"""
This module defines classes to represent and manage global and local explanations
for a given decision method in the context of a legal knowledge base.
"""

from dataclasses import dataclass
import io
from typing import List
from pandas import DataFrame, concat

from py2neo import GraphService, Graph, Subgraph

from explanation_method.decision_method import LegalDecisionMethod
from explanation_method.knowledge_base import KnowledgeBase, LegalKnowledgeBase, references_to
from explanation_method.html_csv_import import CSVImporter, RegelElementParser

@dataclass
class GlobalExplanation:
    """
    Represents a global explanation, which includes the object model, service model,
    and rule model from the Legal Knowledge Base.

    Attributes:
    - graph (Graph): The Neo4j graph associated with the global explanation.
    - models (List[Subgraph]): A list of Subgraph instances representing the models.
    """
    graph: Graph
    models: List[Subgraph]
    kb: KnowledgeBase
    html_parser: RegelElementParser = None

    def match_object_model(self) -> Subgraph:
        """
        Matches the object model in the Neo4j graph.

        Returns:
        - Subgraph: A Subgraph instance representing the object model.
        """
        result = self.graph.run("""
            MATCH (obj:ObjectType)
            OPTIONAL MATCH (obj)<-[prop_rel:property_of]-(prop)
            OPTIONAL MATCH (obj)-[obj_rel:relates_to]-(:ObjectType)
            RETURN obj, prop, prop_rel, obj_rel
        """) 
        return result.to_subgraph()
    
    def match_service_model(self) -> Subgraph:
        """
        Matches the service model in the Neo4j graph.

        Returns:
        - Subgraph: A Subgraph instance representing the service model.
        """
        
        result = self.graph.run("""
            MATCH (ibt:InvoerBerichtType), (obt:UitvoerBerichtType)
            OPTIONAL MATCH (ibt)-[ir:input]->(inp)
            OPTIONAL MATCH (obt)<-[or:output]-(outp)
            RETURN ibt, obt, inp, outp, ir, or
        """) 
        return result.to_subgraph()

    def match_rule_model(self) -> Subgraph:
        """
        Matches the rule model in the Neo4j graph.

        Returns:
        - Subgraph: A Subgraph instance representing the rule model.
        """
        result = self.graph.run("""
            MATCH (regel:Regel)
            OPTIONAL MATCH (regel)-[d:derivation]->(n)
            OPTIONAL MATCH (regel)<-[c:condition]-(m)
            RETURN regel, d, n, c, m
        """) 
        return result.to_subgraph()
    
    @classmethod
    def from_knowledge_base(cls, kb: LegalKnowledgeBase, db_name='global-explanation') -> 'GlobalExplanation':
        """
        Creates a GlobalExplanation instance from a LegalKnowledgeBase.

        Args:
        - kb (LegalKnowledgeBase): A LegalKnowledgeBase instance.

        Returns:
        - GlobalExplanation: A GlobalExplanation instance.
        """
        # NOTE: the global explanation graph is made in the same way as the KB
        # this could be done in a more neat / intuitive way (f.e. by extracting only
        # certain nodes from the kb). I was not able to implement this, but a start
        # of this type of implementation is saved in '
        gb_explanation_kb = LegalKnowledgeBase.from_decision_method(kb.graph.service, kb.decision_method, db_name)       
        gb_explanation = cls(kb.graph.service[db_name], [], gb_explanation_kb)

        gb_explanation.create_object_model()
        gb_explanation.create_rule_model()
        gb_explanation.create_service_model()
        gb_explanation.add_frases()

        gb_explanation.object_model = gb_explanation.match_object_model()
        gb_explanation.rule_model = gb_explanation.match_rule_model()
        gb_explanation.service_model = gb_explanation.match_service_model()
        gb_explanation.models = [gb_explanation.object_model, gb_explanation.rule_model, gb_explanation.service_model]

        gb_explanation.html_parser = RegelElementParser.from_decision_name(kb.decision_method.decision_name)

        return gb_explanation
        
    def create_references(self, print_missed_references=False):
        """
        Creates reference relationships between nodes in the Knowledge Base.

        Args:
        - print_missed_references (bool): If True, prints missed references.
        """
        for model in self.models:
            for (from_dm_node, to_dm_node) in model.reference_list:
                from_kb_node = self.graph.nodes.match("KBNode", alef_id=from_dm_node.id).first()
                to_kb_node = self.graph.nodes.match("KBNode", alef_id=to_dm_node.id).first()

                if from_kb_node and to_kb_node:
                    rel = references_to(from_kb_node, to_kb_node)
                    self.graph.merge(rel)
                else:
                    if print_missed_references:
                        print(f"Note: could not create a reference from {from_dm_node.concept} ({from_dm_node.id}) to {to_dm_node.resolve} ({to_dm_node.id}).")

    def add_frases(self):
        self.graph.run("""
            MATCH (n)-[r:property_of]->(m)
            MERGE (n)<-[r2:has_property]-(m)
            SET r2.frase = r.frase
            RETURN n, m
        """)

        self.graph.run("""
            MATCH ()-[r:derivation]->()
            SET r.frase_en = 'derives', r.frase = 'leidt tot de afleiding van'
            RETURN r;
        """)

        self.graph.run("""
            MATCH ()-[r:condition]->()
            SET r.frase_en = 'is a condition for', r.frase = 'is een voorwaarde voor'
            RETURN r;
        """)

        self.graph.run("""
            MATCH ()-[r:calculation]->()
            SET r.frase_en = 'is used in the calculation of', r.frase = 'wordt gebruikt in de berekening van'
            RETURN r;
        """)

        self.graph.run("""
            MATCH (n:InvoerBerichtType)
            SET n.frase = REPLACE(n.name, 'invoer', '')
            RETURN n;
        """)

        self.graph.run("""
            MATCH (n:UitvoerBerichtType)
            SET n.frase = REPLACE(n.name, 'uitvoer', '')
            RETURN n;
        """)

        self.graph.run("""
            MATCH ()-[r:input]->()
            SET r.frase_en = 'provides', r.frase = 'levert'
            RETURN r;
        """)

        self.graph.run("""
            MATCH ()-[r:output]->()
            SET r.frase_en = 'produces', r.frase = 'produceert'
            RETURN r;
        """)

        self.graph.run("""
            MATCH (obj1:ObjectType)<-[:references_to]-(r1:Rol)<-[:has_child]-(feit:FeitType)-[:has_child]->(r2:Rol)-[:references_to]->(obj2:ObjectType)
            WHERE r1.frase IS NOT NULL
            MERGE (obj1)-[:relates_to {name: feit.name, frase:r1.frase, from:r1.name, from_single:r1.single, to:r2.name, to_single:r2.single}]->(obj2)
            RETURN obj1, r1, feit, r2, obj2;
        """)

        self.graph.run("""
            MATCH (n)-[:condition]->(rule)-[:derivation]->(m)
            MERGE (n)-[r:condition_direct]->(m) 
            SET r.frase_en = 'depends on', r.frase = 'is afhankelijk van';
        """)

        self.graph.run("""
            MATCH (r1:Regel)-[:derivation]->(n)-[:condition]->(r2:Regel)
            MERGE (r1)-[r:condition_direct]->(r2)
            SET r.frase_en = 'depends on', r.frase = 'is afhankelijk van';
        """)

    def create_object_model(self):
        # set label attribute and kenmerk to Variabele
        self.graph.run("""
            MATCH   (var)
            WHERE   var:Attribuut OR var:Kenmerk
            SET     var:Variabele    
            RETURN  var
        """)

        # set all attribute values to False
        self.graph.run("""
            MATCH (atr:Attribuut)
            SET atr.value = 'Onwaar'
            RETURN atr
        """)

        # relationships between objecttypes
        self.graph.run("""
            MATCH (obj1:ObjectType)<-[:references_to]-(r1:Rol)<-[:has_child]-(feit:FeitType)-[:has_child]->(r2:Rol)-[:references_to]->(obj2:ObjectType)
            WHERE r1.frase IS NOT NULL
            MERGE (obj1)-[:relates_to {name: feit.name, frase:r1.frase, from:r1.name, from_single:r1.single, to:r2.name, to_single:r2.single}]->(obj2)
            RETURN obj1, r1, feit, r2, obj2
        """)

        # property relationship between object and variables
        self.graph.run("""
            MATCH (obj:ObjectType)-[]->(prop)
            WHERE prop:Attribuut OR prop:Kenmerk
            MERGE (obj)<-[r:property_of]-(prop)
            RETURN obj, r, prop
        """)

        # frase for property relationship
        self.graph.run("""
            MATCH (o:ObjectType)-[rel:property_of]->(p)
            SET rel.frase = CASE
                WHEN p:Attribuut THEN 'heeft'
                WHEN p:Kenmerk AND p.bijvoeglijk = 'true' THEN 'is'
                WHEN p:Kenmerk AND p.bezittelijk = 'true' THEN 'heeft'
            END
            RETURN o, rel, p
        """)
        
    def create_rule_model(self):
        # TODO: Not all regelspraak patterns are implemented, only the Kenmerktoekenning, Gelijkstelling and 
        # Consistentieregel. These work for the example of the use case, but should probably be specified
        # to include all the ALEF components. 
        # NOTE: I worked around constructie regel for the use case example by changing the name of the 
        # Constructie vast te stellen naheffingsaanslag object to Vast te stellen naheffingsaanslag
        
        # derivation relationships between rule and variables
        self.graph.run("""
            MATCH (r:Regel)-[:has_child*]->(:KenmerkToekenning)-[:references_to]->(k:Kenmerk)
            MERGE (r)-[:derivation {type: 'KenmerkToekenning'}]->(k)
            RETURN r, k
        """)
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child*]->(:Gelijkstelling)-[:has_child]->(:Selectie {role:'links'})-[:has_child*]->(:AttribuutSelector)-[:references_to]->(atr:Attribuut)
            MERGE (regel)-[:derivation {type: 'Gelijkstelling'}]->(atr)
            RETURN regel, atr
        """)
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child*]->(:ConsistentieRegel)-[:has_child*]->(:AttribuutSelector)-[:references_to]->(atr:Attribuut)
            MERGE (regel)-[:derivation {type: 'ConsistentieRegel'}]->(atr)
            RETURN regel, atr   
        """)
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child*]->(:Constructie)-[:has_child]->(:UnivOnderwerp)-[:references_to]->(obj:ObjectType)
            MERGE (regel)-[:derivation {type: 'Constructie'}]->(obj)
            RETURN regel, obj  
        """)

        # condition relationships between variables and rule
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child*]->(av:ActieIndienVoorwaarde)-[:has_child*]->(ev:EnkeleVoorwaarde)-[:has_child]->(rkc:RolOfKenmerkCheck)-[:references_to]->(rk:Kenmerk)
            MERGE (regel)<-[rvw:condition]-(rk)
            SET rvw.ontkenning = CASE
                WHEN rkc.ontkenning = 'true' THEN 'true' ELSE 'false'
            END
            RETURN regel, rk
        """)
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child*]->(av:ActieIndienVoorwaarde)-[:has_child*]->(ev:EnkeleVoorwaarde)-[:has_child*]->(as:AttribuutSelector)-[:references_to]->(atr:Attribuut)
            MERGE (regel)<-[:condition]-(atr)
            RETURN regel, ev
        """)

        # calculation relationships between variables and rule
        self.graph.run("""
            MATCH (regel:Regel)-[:has_child]->(rv:RegelVersie)-[:has_child]->(aiv:ActieIndienVoorwaarde)-[:has_child]->(ac:Gelijkstelling)-[:has_child*]->(:KBNode {role:'rechts'})-[:has_child*]->(:AttribuutSelector)-[:references_to]->(atr:Attribuut)
            MERGE (regel)<-[:calculation]-(atr)
            RETURN regel, atr
        """)

    def create_service_model(self):
        # relationship between service and input messages
        self.graph.run("""
            MATCH (ser:Service)-[:has_child|references_to*]->(bt)
            WHERE bt:UitvoerBerichtType OR bt:InvoerBerichtType
            MERGE (ser)-[_eo:exists_of]->(bt)
            SET _eo.type = CASE
                WHEN bt:UitvoerBerichtType THEN 'UitvoerBericht'
                WHEN bt:InvoerBerichtType THEN 'InvoerBericht'
            END
            RETURN ser, bt
        """)

        # input relationships between input and variables
        self.graph.run("""
            MATCH (ibt:InvoerBerichtType)-[:has_child]->(veld {role:'veld'})-[:references_to]->(ref)
            WHERE ref:Attribuut OR ref: Kenmerk OR ref:InvoerBerichtType
            MERGE (ibt)-[:input]->(ref)
            SET veld.verplicht = CASE
                WHEN veld.verplicht = 'true' THEN 'true' ELSE 'false'
            END
            RETURN ibt, veld, ref
        """)

        # output relationships between variables and output
        self.graph.run("""
            MATCH (ubt:UitvoerBerichtType)-[:has_child]->(veld {role:'veld'})-[:references_to]->(ref)
            WHERE ref:Attribuut OR ref: Kenmerk OR ref:UitvoerBerichtType
            MERGE (ubt)<-[:output]-(ref)
            RETURN ubt, veld, ref
        """)

    def service_check_input(self, output_type='warning'):
        result = self.graph.run("""
        MATCH (ibt:InvoerBerichtType)-[:input]->(var_in:Variabele)
        RETURN 
            ibt.frase AS Invoer,
            var_in.name AS Variabele,
            EXISTS {
                MATCH path=(var_in)-[:condition|derivation|calculation*]->(var_out:Variabele)-[:output]->(ubt:UitvoerBerichtType)
                RETURN path
            } AS Path
        """).to_data_frame()

        if output_type == 'warning':
            warnings = []
            for row in result.itertuples():
                if row.Path == False:
                    warning = f"<li>Er is geen pad gevonden van {row.Variabele} vanuit invoer {row.Invoer} naar de uitvoer.</li>"
                    warnings.append(warning)

            if warnings:
                warnings_html = "<ul>" + "".join(warnings) + "</ul>"
                return f"<div>Let op: er zijn invoerberichten gevonden zonder pad naar de uitvoer. Controleer of er voldoende regels aanwezig zijn.</div>{warnings_html}"
            else:
                return f"<div>Voor elke variabele in de invoerberichten is een pad naar de uitvoer gevonden.</div>"

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result
        
    def service_check_output(self, output_type='warning'):
        result = self.graph.run("""
        MATCH (var_out:Variabele)-[:output]->(ubt:UitvoerBerichtType)
        RETURN 
            ubt.frase AS Uitvoer,
            var_out.name AS Variabele,
            EXISTS {
                MATCH path=(:InvoerBerichtType)-[:input|condition|derivation|calculation*]->(var_out)
                RETURN path
            } AS Path
        """).to_data_frame()
        if output_type == 'warning':
            warnings = []
            for row in result.itertuples():
                if row.Path == False:
                    warning = f"<li>{row.Variabele} ({row.Uitvoer})</li>"
                    warnings.append(warning)

            if warnings:
                warnings_html = "<ul>" + "".join(warnings) + "</ul>"
                return f"<div>Let op: er zijn uitvoerberichten gevonden zonder pad vanuit de invoer. Controleer of er voldoende invoervariabelen en regels aanwezig zijn.</div>{warnings_html}"
            else:
                return f"<div>Voor elke variabele in de uitvoerberichten is een pad vanuit de invoer gevonden.</div>"

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result
    
    def path_check_inoutput(self, output_type='warning'):
        result = self.graph.run("""
            MATCH (inout)
            WHERE inout:InvoerBerichtType OR inout:UitvoerBerichtType
            RETURN 
                CASE 
                    WHEN inout:InvoerBerichtType THEN 'Invoer'
                    WHEN inout:UitvoerBerichtType THEN 'Uitvoer'
                END AS Type,
                inout.name AS Bericht, 
                EXISTS {
                    MATCH path=(:Service)-[:exists_of]->(inout)
                    RETURN path
            } AS Path
            """).to_data_frame()
        
        if output_type == 'warning':
            warnings = []
            for row in result.itertuples():
                if row.Path == False:
                    warning = f"<li>Er is geen pad gevonden naar {row.Type} {row.Bericht}.</li>"
                    warnings.append(warning)

            if warnings:
                warnings_html = "<ul>" + "".join(warnings) + "</ul>"
                return f"<div>Let op: in- en/of uitvoerberichten gevonden zonder pad naar de service. Controleer of elk bericht wordt gebruikt.</div>{warnings_html}"
            else:
                return f"<div>Alle in- en uitvoerberichten worden door de service gebruikt.</div>"

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result

    def path_check_variables(self, output_type='warning'):
        '''
        Check whether a variable (Attribuut/Kenmerk) is included in an input message or assigned a value in a derivation rule/table.
        
        Parameters:
            output_type (str): The type of output to return. Must be one of 'warning', 'html_table', or 'pd_table'.
            
        Returns:
            If output_type is 'warning', returns an HTML string containing warning messages for variables that are unused or unassigned.
            If output_type is 'html_table', returns a pandas dataframe as an HTML table.
            If output_type is 'pd_table', returns a pandas dataframe.
        '''
        result = self.graph.run("""
            MATCH (obj:ObjectType)-->(var:Variabele)
            RETURN DISTINCT
                obj.name AS Object,
                var.name AS Variabele,
                CASE 
                    WHEN EXISTS {
                        MATCH   path=(var)-[:condition]->(:Regel)
                        RETURN  path
                        } THEN 'Voorwaarde'
                    WHEN EXISTS {
                        MATCH   path=(var)-[:calculation]->(:Regel)
                        RETURN  path
                        } THEN 'Berekening'
                    WHEN EXISTS {
                        MATCH   path=(var)-[:output]->(:UitvoerBerichtType)
                        RETURN  path
                        } THEN 'Uitvoer'
                    ELSE 'Ongebruikt'
                END AS Path  
            """).to_data_frame()
        
        if output_type == 'warning':
            warnings_path = []
            for row in result.itertuples():
                if row.Path == 'Ongebruikt':
                    warning = f"<li>{row.Variabele} {row.Object}</li>"
                    warnings_path.append(warning)

            warnings_html = ""
            if warnings_path:
                warnings_html += "<div><br>Let op: de volgende attributen / kenmerken worden niet gebruikt in een regel, een flow of doorgegeven van invoer naar uitvoer:</div>"
                warnings_html +=  "<ul>" + "".join(warnings_path) + "</ul>"
                warnings_html += "<div>Indien het attribuut / kenmerk overbodig is kun je het beter verwijderen.</div>"
            else:
                warnings_html += "<div>Alle variabelen worden gebruikt in een regel, een flow of doorgegeven van invoer naar uitvoer.<br></div>"
            
            return warnings_html

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result
        

    def assignment_check_variables(self, output_type='warning'):
        '''
        Check whether a variable (Attribuut/Kenmerk) is included in an input message or assigned a value in a derivation rule/table.
        
        Parameters:
            output_type (str): The type of output to return. Must be one of 'warning', 'html_table', or 'pd_table'.
            
        Returns:
            If output_type is 'warning', returns an HTML string containing warning messages for variables that are unused or unassigned.
            If output_type is 'html_table', returns a pandas dataframe as an HTML table.
            If output_type is 'pd_table', returns a pandas dataframe.
        '''
        result = self.graph.run("""
            MATCH (var:Variabele)
            RETURN 
                var.name AS Naam,
                CASE
                    WHEN EXISTS {
                        MATCH   path1=(:InvoerBerichtType)-[:input]->(var), path2=(:Regel)-[:derivation]->(var)
                        RETURN  path1, path2
                        } THEN 'Invoer en Regel'
                    WHEN EXISTS {
                        MATCH   path=(:InvoerBerichtType)-[:input]->(var)
                        RETURN  path
                        } THEN 'Invoer'
                    WHEN EXISTS {
                        MATCH   path=(:Regel)-[:derivation]->(var)
                        RETURN  path
                        } THEN 'Regel'
                    ELSE 'Geen assignment'
                END AS Assignment
            """).to_data_frame()
        
        if output_type == 'warning':
            warnings_assignment = []
            for row in result.itertuples():
                if row.Assignment == 'Geen assignment':
                    warning = f"<li>{row.Naam}</li>"
                    warnings_assignment.append(warning)

            warnings_html = ""
            if warnings_assignment:
                warnings_html += "<div><br>Let op: de volgende attributen / kenmerken hebben geen waarde toegekend gekregen:</div>"
                warnings_html +=  "<ul>" + "".join(warnings_assignment) + "</ul>"
                warnings_html += "<div>Zorg ervoor dat elk attribuut / kenmerk een waarde krijgen via een invoerbericht of een afleidingsregel / tabel.<br></div>"
            else:
                warnings_html += "<div><br>Alle attributen / kenmerken hebben een waarde toegekend gekregen.<br></div>"

            return warnings_html

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result
        
    def logic_check_rules(self, output_type='warning'):
        # TODO: Actually check for 'tegenstrijdige voorwaarden'
        result = self.graph.run("""
            MATCH (var:Variabele)-[:condition]->(regel:Regel)
            WITH regel, var
            MATCH path=(regel)-[:has_child*]->()-[:references_to]->(var)
            RETURN 
                regel.name AS Regel, 
                var.name AS VariabeleInConditie, 
                COUNT(DISTINCT path) as AantalPaden
        """).to_data_frame()

        if output_type == 'warning':
            warnings = []
            has_warnings = False
            for row in result.itertuples():
                if row.AantalPaden > 1:
                    warning = f"<li>Dubbelgebruik van {row.VariabeleInConditie}:<br><br></li>"
                    warnings.append(warning)
                    regel_html = self.html_parser.return_html(row.Regel, string=True)
                    warnings.append(regel_html)
                    has_warnings = True

            if has_warnings:
                instructions = "<b>Instructie</b><br>" \
                            "Een regel heeft tegenstrijdige voorwaarden waardoor de regel altijd wordt uitgevoerd, indien aan één van de volgende voorwaarden is voldaan:<br>" \
                            "&emsp;• aan alle volgende voorwaarden is voldaan:<br>" \
                            "&emsp;&emsp;o de regelvoorwaarden sluiten elkaar zuiver uit*<br>" \
                            "&emsp;&emsp;o de regelvoorwaarden zijn geplaatst op hetzelfde niveau van nesting<br>" \
                            "&emsp;&emsp;o aan tenminste één van de regelvoorwaarden moet worden voldaan<br>" \
                            "&emsp;• aan alle volgende voorwaarden is voldaan:<br>" \
                            "&emsp;&emsp;o de regelvoorwaarden sluiten elkaar zuiver uit*<br>" \
                            "&emsp;&emsp;o de regelvoorwaarden zijn zelf onderdeel van verschillende niveaus van nesting<br>" \
                            "&emsp;&emsp;o voor de niveaus van nesting van de voorwaarden geldt dat aan tenminste één van de regelvoorwaarden moet worden voldaan<br><br>" \
                            "\n* Wanneer is er sprake van twee voorwaarden die elkaar zuiver uitsluiten?<br>" \
                            "&emsp;• twee voorwaarden met een booleaans attribuut sluiten elkaar zuiver uit als de één waar is en de ander ongelijk aan waar.<br>" \
                            "&emsp;• twee voorwaarden met een numeriek attribuut sluiten elkaar zuiver uit als de waardenreeksen niet overlappen en de grenswaarde van de ene aansluit aan de grenswaarde van de andere: Bijv. ‘kleiner dan 0’ en ‘groter of gelijk aan 0’ sluiten elkaar zuiver uit, maar ‘kleiner dan 0’ en ‘groter dan 10’ sluiten elkaar niet zuiver uit.<br>" 
                warnings_html = "<ul>" + "".join(warnings) + "</ul>"
                html_text = f"<div>Let op: de volgende regels gebruiken hetzelfde attribuut voor verschillende voorwaarden. Controleer of dit niet tot tegenstrijdige voorwaarden heeft geleid (zie Instructie hieronder). {warnings_html}<br>{instructions}<br><br>" 
            else:
                html_text = "<div>Er zijn geen regels gevonden waarin hetzelfde attribuut voor verschillende voorwaarden wordt gebruikt.</div>"
            return html_text

        elif output_type == 'html_table':
            return result.to_html()
        elif output_type == 'pd_table':
            return result
        
    def check_conflicting_conditions(conditions):
        for i in range(len(conditions)):
            for j in range(i+1, len(conditions)):
                if conditions[i]['type'] != conditions[j]['type']:
                    continue
                if conditions[i]['type'] == 'bool' and conditions[i]['value'] != conditions[j]['value']:
                    return True
                elif conditions[i]['type'] == 'num':
                    if (conditions[i]['upper'] is not None and conditions[j]['lower'] is not None and conditions[i]['upper'] < conditions[j]['lower']) or \
                    (conditions[i]['lower'] is not None and conditions[j]['upper'] is not None and conditions[i]['lower'] > conditions[j]['upper']):
                        return True
        return False

        
@dataclass
class LocalExplanation:
    """
    Represents a local explanation.

    Attributes:
    - graph (Graph): The Neo4j graph associated with the local explanation.
    """
    graph: Graph
    models: List[Subgraph]
    global_explanation: GlobalExplanation
    html_parser: RegelElementParser = None

    @classmethod
    def from_knowledge_base(cls, kb: LegalKnowledgeBase) -> 'LocalExplanation':
        """
        Creates a GlobalExplanation instance from a LegalKnowledgeBase.

        Args:
        - kb (LegalKnowledgeBase): A LegalKnowledgeBase instance.

        Returns:
        - GlobalExplanation: A GlobalExplanation instance.
        """
        # NOTE: the local explanation graph is made in the same way as the Global one
        # this could be done in a more neat / intuitive way (f.e. by extracting only
        # certain nodes from the global expl). I was not able to implement this, but 
        # a start of this type of implementation is saved in 'unfinished code' 
        lc_explanation_ge = GlobalExplanation.from_knowledge_base(kb, db_name='local-explanation')       
        lc_explanation = cls(kb.graph.service['local-explanation'], [], lc_explanation_ge)
        lc_explanation.models = lc_explanation.global_explanation.models
        lc_explanation.html_parser = RegelElementParser.from_decision_name(kb.decision_method.decision_name)
        
        return lc_explanation
    
    def create_html_explanation(self):
        with io.open('../html/local_explanation.html', 'w', encoding='utf-8') as file:
            file.write('<html>\n')
            # Write the HTML content to the file
            file.write(self.return_output())
            file.write('\n</html>')

    def what(self, name, obj_name, df=False):
        result = self.graph.run(f"""
            MATCH   (var:Variabele {{name: '{name}'}})<-[:has_property]-(obj:ObjectType {{name: '{obj_name}'}})
            RETURN  
                "Het " + var.name + " van de " + obj.name + " is " + var.waarde + "." AS result
        """).to_data_frame()
        return result if df else result['result'][0]
    
    def what_decisions(self, df=False):
        result = self.graph.run("""
            MATCH   (n)-[rel]->(var:Variabele)-[:output]->(uit:UitvoerBerichtType)
            WHERE   n:Regel AND n.waarde = 'fired' AND rel:derivation OR n:InvoerBerichtType AND rel:input
            WITH    n, var, uit
            MATCH   (obj:ObjectType)-[:has_property]->(var)
            RETURN  
                uit.frase AS Uitvoer,
                var.name + " van de " + obj.name AS Variabele, 
                var.waarde AS Waarde
        """).to_data_frame()
        return result if df else result.to_html()
    
    def what_personal_data(self, df=False):
        result = self.graph.run("""
            MATCH   (in:InvoerBerichtType)-[:input]->(var:Variabele)<-[:has_property]-(obj:ObjectType)
            RETURN  
            in.frase as Invoer,
            var.name + " van de " + obj.name AS Variabele,
            var.waarde as Waarde
        """).to_data_frame()
        return result if df else result.to_html()
    
    def what_rules(self, df=False, negative=False):
        operator = "<>" if negative else "="

        result = self.graph.run(f"""
            MATCH   (n: Regel)
            WHERE   n.waarde {operator} 'fired'
            RETURN  n.name as Regel, n.geldigheid as Geldigheid, n.bron as Bron
        """).to_data_frame()

        return result if df else [self.html_parser.return_html(rule) for rule in result['Regel'].values]            
        
    def why_decision(self, name, obj_name, df=False, negative=False):
        operator = "<>" if negative else "="

        result = self.graph.run(f"""
            MATCH   (cd_var:Variabele)-[:condition]->(regel:Regel)-[:derivation]->(var:Variabele {{name: '{name}'}})<-[:has_property]-(obj:ObjectType {{name: '{obj_name}'}})
            WHERE   regel.waarde {operator} 'fired'
            RETURN  regel.name as Regel, cd_var.name as AfhankelijkVan, var.name as Bepaalt
        """).to_data_frame()
        
        return result if df else [self.html_parser.return_html(rule) for rule in result['Regel'].unique()]  

    def why_paths(self, name, obj_name, df=False, negative=False):
        operator = "<>" if negative else "="

        result = self.graph.run(f"""
            MATCH   path=(in:InvoerBerichtType)-[:input]->(:Variabele)-[:derivation|condition*]->(n:Variabele {{name:'{name}'}})<-[:has_property]-(obj:ObjectType {{name: '{obj_name}'}})
            WITH    collect(path) as paths
            UNWIND  paths as path    
            RETURN  [node in nodes(path) WHERE 'Regel' IN labels(node) | node.name] as nodes
        """).to_data_frame()

        if df: 
            return result
        else:
            unique_rules = []
            for rules in result.nodes:
                for rule in reversed(rules):
                    if rule not in unique_rules:
                        unique_rules.append(rule)

            return [self.html_parser.return_html(rule) for rule in unique_rules]

        
    def question_answering(self):
        NotImplemented


@dataclass
class ExplanationMethod:
    """
    Represents an explanation method for a legal decision.

    Attributes:
    - decision_name (str): The name of the legal decision.
    - decision_method (LegalDecisionMethod): The LegalDecisionMethod instance.
    - dbms (GraphService): The Graph Database Management System connection.
    - knowledge_base (LegalKnowledgeBase): The LegalKnowledgeBase instance.
    - global_explanation (GlobalExplanation): The GlobalExplanation instance.
    - local_explanation (LocalExplanation): The LocalExplanation instance.
    """
    decision_name: str
    decision_method: LegalDecisionMethod

    dbms: GraphService
    knowledge_base: LegalKnowledgeBase
    global_explanation: GlobalExplanation
    local_explanation: LocalExplanation

    @classmethod
    def from_decision_name(cls, decision_name: str, uri='bolt://localhost:7687', user = 'neo4j', password = 'uitlegbaarheid'):
        decision_method = LegalDecisionMethod.from_decision_name(decision_name)
        gdbms = GraphService(uri, auth=(user, password))
        knowledge_base = LegalKnowledgeBase.from_decision_method(gdbms, decision_method)
        global_explanation = GlobalExplanation.from_knowledge_base(knowledge_base)
        local_explanation = LocalExplanation.from_knowledge_base(knowledge_base)

        explanation_method = cls(decision_name, decision_method, gdbms, knowledge_base, global_explanation, local_explanation)
        
        # NOTE for now, some additional information is added through
        # a csv import. Ideally, this information is received from the KB
        # and through a direction connection with the decision method, 
        # but this has yet to be implemented.
        explanation_method.csv_import() 

        return explanation_method
    
    def csv_import(self):
        csv_importer = CSVImporter.from_decision_name(self.decision_name)
        csv_importer.update_graph(self.global_explanation.graph)
        csv_importer.update_graph(self.local_explanation.graph, local=True)

    def delete_all_graph(self):
        self.knowledge_base.graph.delete_all()
        self.global_explanation.graph.delete_all()
        self.local_explanation.graph.delete_all()

