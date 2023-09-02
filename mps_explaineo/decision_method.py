"""
    This code defines a set of data classes and methods for parsing and representing a
    (legal) rule-based and model-driven decision method with models stored in XML files. 
    It includes classes for representing decision properties, references, nodes, models, 
    and methods, as well as methods for parsing XML files and creating instances of 
    these classes.
"""

from dataclasses import dataclass, field
import xml.etree.ElementTree as ET
import re

@dataclass
class DecisionProperty:
    """
    Represents a property from within a decision node (f.e. the name of a node).
    
    Attributes:
    - role (str): The role of the property.
    - value (str): The value of the property.
    - name (str): The name of the property.
    """

    role: str
    value: str
    name: str
        
    def __str__(self, indent=0):
        return ' ' * (indent + 2) + f'{self.name}: {self.value}\n'

@dataclass
class DecisionReference:
    """
    Represents a reference within a decision node (towards another node).
    
    Attributes:
    - role (str): The role of the reference.
    - to (str): The node this reference points to.
    - resolve (str): The resolution value of the reference.
    """

    role: str
    to: str
    resolve: str

    @property
    def id(self):
        return re.sub(r'^[^:]*:', '', self.to)

    def __str__(self, indent=0):
        return ' ' * (indent + 2) + f'reference: {self.resolve}\n'
    
@dataclass
class DecisionNode:
    """
    Represents a node in the decision model.
    
    Attributes:
    - id (str): The unique identifier of the node.
    - concept_xml (object): The XML object representing the concept associated with the node.
    - role_xml (object): The XML object representing the role associated with the node.
    - properties (list[DecisionProperty]): A list of properties associated with the node.
    - references (list[DecisionReference]): A list of references associated with the node.
    - children (list[DecisionNode]): A list of child nodes associated with the node.
    """
    
    id: str
    concept_xml: object
    role_xml: object

    properties: list[DecisionProperty] = field(default_factory=list)
    references: list[DecisionReference] = field(default_factory=list) 
    children: list = field(default_factory=list) # list of DecisionNodes

    def __str__(self, indent=0):
        string = ''
        string += ' ' * indent + f'{self.concept}\n'
        for prop in self.properties:
            string += prop.__str__()

        for ref in self.references:
            string += ref.__str__()

        for child_node in self.children:
            string += child_node.__str__(indent=indent + 2)
        
        return string
    
    @property
    def name(self):
        for prop in self.properties:
            if prop.name == 'name':
                return prop.value
        else:
            return None
        
    @property
    def concept(self):
        concept_name = self.concept_xml.get('name')
        match = re.search(r'\w+$', concept_name)
        concept = match.group(0) if match else concept_name
        return concept
    
    @property
    def role(self):
        if self.role_xml == 'root':
            return 'root'
        role_name = self.role_xml.get('name') 
        match = re.search(r'\w+$', role_name)
        role = match.group(0) if match else role_name
        return role
    
    @property
    def ref(self):
        refnames = []
        for reference in self.references:
            refnames += [reference.resolve]
        if len(refnames) == 1:
            return refnames[0]
        else:
            raise ValueError(f'Found zero or multiple references: {refnames}.')

class DecisionModel:
    """
    Represents a decision model used by a Decision Method. Provides methods for 
    parsing the corresponding XML files and creating instances of DecisionNode to 
    build Python objects representing the elements of a decision model.
    
    Attributes:
    - decision_name (str): The name of the decision model.
    - model_name (str): The name of the specific model within the decision model.
    - root_concept (str): The root concept name of the decision model.
    - filename (str): The path to the XML file containing the decision model data.
    - concepts (dict): A dictionary of concepts parsed from the XML file.
    - nodes (list[DecisionNode]): A list of nodes in the decision model.
    """
    
    def __init__(self, decision_name, model_name, root_concept):
        self.decision_name = decision_name
        self.model_name = model_name
        self.root_concept = root_concept

        self.filename = f"../data/{decision_name}/models/{model_name}.mps"
        self.concepts = self.parse_concepts()
        self.nodes = self.parse_nodes()
    
    @staticmethod
    def parse_concept_elements(concept, library):
        """
        Parse the properties of an XML concept and update the library.

        Args:
        - concept (xml.etree.ElementTree.Element): The XML concept to parse
        - library (dict): A dictionary holding the elements indexed by different keys

        Returns:
        - dict: The updated library with parsed properties, references, and children
        """
        for elem_type in ['property', 'reference', 'child']:
            for elem in concept.findall(f'./{elem_type}'):
                name = re.search(r'\w+$', concept.get('name')).group(0)
                library[elem_type]['name'][name] = elem
                library[elem_type]['id'][elem.get('id')] = elem
                library[elem_type]['index'][elem.get('index')] = elem
                
                library[elem_type]['concept'][concept] = elem
                library['concept'][elem_type][elem] = concept
        
        return library

    def parse_concepts(self):
        """
        Parse an XML file and create a library to store the elements by name, ID, and index.

        Returns:
        - dict: A dictionary of the elements in the XML file, indexed by name, ID, and index
        """
        tree = ET.parse(self.filename)
        root = tree.getroot()

        concept_library = {"name": {}, "id": {}, "index": {}, 'property': {}, 'reference': {}, 'child': {}}
        elem_library = {"name": {}, "id": {}, "index": {}, 'concept': {}}
        library = {'concept': concept_library , 'property': elem_library, 'reference': elem_library, 'child': elem_library}
        
        for language in root.findall('.//language'):
            for concept in language.findall('concept'):
                name = re.search(r'\w+$', concept.get('name')).group(0)
                library['concept']['name'][name] = concept
                library['concept']['index'][concept.get('index')] = concept
                library['concept']["id"][concept.get('id')] = concept
                
                library = self.parse_concept_elements(concept, library)

        return library
    
    def create_node(self, xml_node):
        """
        Creates a DecisionNode object from an ElementTree XML node.

        Args:
        - xml_node (xml.etree.ElementTree.Element): ElementTree XML node to create a DecisionNode from

        Returns:
        - DecisionNode: DecisionNode object created from xml_node
        """
    
        node_id = xml_node.get('id')
        node_concept_xml = self.concepts['concept']['index'][xml_node.get('concept')]
        if not xml_node.get('role'):
            node = DecisionNode(node_id, node_concept_xml, 'root')
        else:
            node_role_xml = self.concepts['child']['index'][xml_node.get('role')]
            node = DecisionNode(node_id, node_concept_xml, node_role_xml)

        # Loop through all properties of the xml_node and create Property objects to append to node's properties list
        for xml_property in xml_node.findall('property'):
            prop_role = xml_property.get('role')
            prop_value = xml_property.get('value')
            prop_name = self.concepts['property']['index'][prop_role].get('name') # use name of corresponding concept_property
            
            prop = DecisionProperty(prop_role, prop_value, prop_name)
            node.properties.append(prop)

        # Loop through all properties of the xml_node and create Property objects to append to node's properties list
        for xml_reference in xml_node.findall('ref'):
            ref_role = xml_reference.get('role')
            ref_node = xml_reference.get('node')
            if ref_node == None:
                ref_node = xml_reference.get('to')
            ref_resolve = xml_reference.get('resolve')
            
            ref = DecisionReference(ref_role, ref_node, ref_resolve)
            node.references.append(ref)
            
        # Loop through all child nodes of the xml_node and create Node objects to append to node's nodes list
        for xml_child_node in xml_node.findall('node'):
            child_node = self.create_node(xml_child_node)
            node.children.append(child_node)

        return node   

    def parse_nodes(self):
        """
        Parses an ElementTree XML tree to create Node objects.

        Args:
        - xml_file (str): path to XML file to parse
        - objecttype_name (str): name of the object type to extract nodes from
        - concepts_by_index (dict): A dictionary mapping concept indexes to their names.

        Returns:
        - list: list of Node objects created from XML file
        """
        tree = ET.parse(self.filename)
        root = tree.getroot()
        
        nodes = []
        # Loop through all nodes (with concept name of objecttype) and create Node objects to append to nodes list
        if not self.root_concept:
            for xml_node in root.findall('node'):
                node = self.create_node(xml_node)
                nodes.append(node)
        else:
            root_index = self.concepts['concept']['name'][self.root_concept].get('index')
            for xml_node in root.findall(f".//*[@concept='{root_index}']"):
                node = self.create_node(xml_node)
                nodes.append(node)
        
        return nodes

@dataclass
class DecisionMethod:
    """
    Represents a decision method that consists of multiple decision models.
    
    Attributes:
    - decision_name (str): The name of the decision method.
    - decision_models (list[DecisionModel]): A list of decision models associated with the decision method.
    """

    decision_name: str
    decision_models: list[DecisionModel]

@dataclass
class LegalDecisionMethod(DecisionMethod):
    """
    Represents a legal decision method with specific object, rule, service, and test models.
    
    Attributes:
    - objectmodel (DecisionModel, optional): The object model associated with the legal decision method.
    - regelmodel (DecisionModel, optional): The rule model associated with the legal decision method.
    - servicemodel (DecisionModel, optional): The service model associated with the legal decision method.
    - testmodel (DecisionModel, optional): The test model associated with the legal decision method.
    """

    object_model: DecisionModel = None
    regel_model: DecisionModel = None
    service_model: DecisionModel = None
    test_model: DecisionModel = None

    @classmethod
    def from_decision_name(cls, decision_name):
        legal_dm = cls(decision_name, [])

        legal_dm.object_model = DecisionModel(decision_name, 'gegevens', None)
        legal_dm.regel_model = DecisionModel(decision_name, 'regels', None)
        legal_dm.service_model = DecisionModel(decision_name, 'services', None)
        legal_dm.test_model = DecisionModel(decision_name, 'tests', 'ServiceTestSet')

        legal_dm.decision_models = [legal_dm.object_model, legal_dm.regel_model, legal_dm.service_model, legal_dm.test_model]
        
        return legal_dm
 

