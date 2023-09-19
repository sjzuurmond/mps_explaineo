"""
    This module provides classes and methods for representing a knowledge base (KB)
    using decision models and legal decision methods. The classes define the structure
    and relationships between nodes and subgraphs in the KB and provide methods for
    manipulating and extracting information from the KB.
"""

from dataclasses import dataclass
from py2neo import Graph, Subgraph, Node, Relationship

from mps_explaineo.decision_method import LegalDecisionMethod, DecisionMethod, DecisionModel

# relationship classes for in the KB
class has_child(Relationship): pass
class references_to(Relationship): pass
class property_of(Relationship): pass
class relates_to(Relationship): pass

class GraphUnbinder:
    """
    A class that provides methods for creating unbound Node, Relationship, and Subgraph objects from bound objects.
    """
    @staticmethod
    def unbind_node(node: Node):
        """
        Takes a bound Node object and returns an unbound Node object with the same labels and properties.
        """
        return Node(*node.labels, **node)

    @staticmethod
    def unbind_relationship(rel: Relationship):
        """
        Takes a bound Relationship object and returns an unbound Relationship object with the same type and properties.
        """
        start_node = GraphUnbinder.unbind_node(rel.start_node)
        end_node = GraphUnbinder.unbind_node(rel.end_node)
        return rel.__class__(start_node, end_node, **rel)

    @staticmethod
    def unbind_subgraph(subgraph: Subgraph):
        """
        Takes a bound Subgraph object and returns an unbound Subgraph object with the same nodes and relationships.
        """
        unbound_nodes = [GraphUnbinder.unbind_node(node) for node in subgraph.nodes]
        unbound_rels = [GraphUnbinder.unbind_relationship(rel) for rel in subgraph.relationships]
        return Subgraph(nodes=unbound_nodes, relationships=unbound_rels)
    
@dataclass
class KnowledgeBaseModel: 
    """
    Contains a subgraph representing a DecisionModel.
    
    Attributes:
    - decision_model (DecisionModel): A DecisionModel instance.
    - subgraph (Subgraph): A Subgraph instance representing the DecisionModel.
    - reference_list (list): A list of reference relationships between nodes.
    - root_nodes (list, optional): A list of root nodes for the KnowledgeBaseModel.
    """
    decision_model: DecisionModel
    subgraph: Subgraph

    reference_list: list
    root_nodes: list = None

    @classmethod
    def from_decision_model(cls, decision_model):
        """
        Creates a KnowledgeBaseModel instance from a DecisionModel.

        Args:
        - decision_model (DecisionModel): A DecisionModel instance.

        Returns:
        - KnowledgeBaseModel: A KnowledgeBaseModel instance.
        """

        kb_model = cls(decision_model, Subgraph(), [])
        kb_model.root_nodes = [kb_model.create_node(dm_node) for dm_node in decision_model.nodes]
        
        return kb_model
    
    def create_node(self, dm_node):
        """
        Creates a KBNode from a DecisionModel node.

        Args:
        - dm_node (DecisionNode): A DecisionNode instance.

        Returns:
        - Node: A Node instance representing a KBNode.
        """

        kb_node = Node('KBNode')
        kb_node.add_label(dm_node.concept)
        kb_node.add_label(self.decision_model.model_name)

        kb_node['alef_id'] = dm_node.id
        kb_node['role'] = dm_node.role
        kb_node['name'] = dm_node.name

        if dm_node.properties:
            for alef_prop in dm_node.properties:
                kb_node[alef_prop.name] = alef_prop.value
                
        self.subgraph = self.subgraph | kb_node

        if dm_node.children:
            for dm_child in dm_node.children:
                kb_child = self.create_node(dm_child)
                rel = has_child(kb_node, kb_child)
                self.subgraph = self.subgraph | kb_node | rel
            
        if dm_node.references:
            for dm_ref in dm_node.references:
                ref_node = self.get_node_by_property('alef_id', dm_ref.id)
                if not ref_node:
                    self.reference_list += [(dm_node, dm_ref)]
                else:
                    ref = references_to(kb_node, ref_node)
                    self.subgraph = self.subgraph | ref

        return kb_node
    
    def get_node_by_property(self, property_name, property_value):
        for node in self.subgraph.nodes:
            if property_name in node and node[property_name] == property_value:
                return node
        return None
        
@dataclass
class KnowledgeBase:
    """
    Represents a Knowledge Base containing multiple KnowledgeBaseModel instances.

    Attributes:
    - decision_method (DecisionMethod): A DecisionMethod instance.
    - graph (Graph): A Graph instance representing the Knowledge Base.
    - models (list[KnowledgeBaseModel]): A list of KnowledgeBaseModel instances.
    """

    decision_method: DecisionMethod
    graph: Graph
    models: list[KnowledgeBaseModel]

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

    def delete_all(self):
        """
        Deletes all nodes and relationships in the Knowledge Base.
        """
        self.graph.delete_all()
        print("You have deleted the Knowledge Base.")

@dataclass
class LegalKnowledgeBase(KnowledgeBase):
    """
    Represents a Legal Knowledge Base containing multiple KnowledgeBaseModel instances.

    Attributes:
    - decision_method (LegalDecisionMethod): A LegalDecisionMethod instance.
    - objectmodel (KnowledgeBaseModel, optional): An ObjectModel instance.
    - regelmodel (KnowledgeBaseModel, optional): A RegelModel instance.
    - servicemodel (KnowledgeBaseModel, optional): A ServiceModel instance.
    - testmodel (KnowledgeBaseModel, optional): A TestModel instance.
    """

    decision_method: LegalDecisionMethod

    object_model: KnowledgeBaseModel = None
    regel_model: KnowledgeBaseModel = None
    service_model: KnowledgeBaseModel = None
    test_model: KnowledgeBaseModel = None

    @classmethod
    def from_decision_method(cls, gdbms, decision_method: LegalDecisionMethod, db_name='knowledge-base', print_missed_references=False):
        """
        Creates a LegalKnowledgeBase instance from a LegalDecisionMethod.

        Args:
        - gdbms (GraphService): A Graph instance representing the Knowledge Base.
        - decision_method (LegalDecisionMethod): A LegalDecisionMethod instance.
        - print_missed_references (bool, optional): If True, prints missed references.

        Returns:
        - LegalKnowledgeBase: A LegalKnowledgeBase instance.
        """

        legal_kb = cls(decision_method, gdbms[db_name], [])
        
        legal_kb.object_model = KnowledgeBaseModel.from_decision_model(decision_method.object_model)
        legal_kb.regel_model = KnowledgeBaseModel.from_decision_model(decision_method.regel_model)
        legal_kb.service_model = KnowledgeBaseModel.from_decision_model(decision_method.service_model)
        legal_kb.test_model = KnowledgeBaseModel.from_decision_model(decision_method.test_model)
        legal_kb.models = [legal_kb.object_model, legal_kb.regel_model, legal_kb.service_model, legal_kb.test_model]
    
        [legal_kb.graph.merge(model.subgraph, "KBNode", "alef_id") for model in legal_kb.models]
        legal_kb.create_references(print_missed_references)
        
        return legal_kb





        

