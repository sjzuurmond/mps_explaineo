import os
from bs4 import BeautifulSoup
from IPython.display import HTML
from dataclasses import dataclass

from pandas import DataFrame, read_csv

@dataclass
class RegelElementParser:
    directory: str
    element_list: list = None
    element_dict: dict = None

    @classmethod
    def from_decision_name(cls, decision_name):
        directory = f'../data/{decision_name}/html/regels/'
        parser = cls(directory)
        parser.element_list = parser.parse_files(directory)
        parser.element_dict = {elem.span.text.strip(): elem for elem in parser.element_list}

        return parser

    def parse_files(self, directory):
        elements = []
        srcs = self.get_file_paths(directory)
        for src in srcs:
            soup = self.get_html_soup(src)
            elements += soup.find_all(class_='regel')
        
        elements = self.remove_hrefs(elements)
        return elements

    def return_html(self, name, string=False):
        elem = str(self.element_dict[name])
        return elem if string else HTML(elem)

    @staticmethod
    def get_file_paths(directory):
        paths = []
        for (root, _, files) in os.walk(directory):
            for file in files:
                paths.append(os.path.join(root, file))
                
        return paths
    
    @staticmethod
    def get_html_soup(src):
        with open(src) as html_page:
            return BeautifulSoup(html_page, 'html.parser')
        
    @staticmethod
    def remove_hrefs(elements):
        for elem in elements:
            for tag in elem.find_all():
                if tag.has_attr("href"):
                    del tag["href"]

        return elements
    

@dataclass
class CSVImporter:
    variables_df: DataFrame
    rules_df: DataFrame
    conditions_df: DataFrame
    derivations_df: DataFrame

    @classmethod
    def from_decision_name(cls, decision_name):
        variables_df = read_csv(f'../data/{decision_name}/csv/variables.csv', header=0, delimiter=';')
        rules_df = read_csv(f'../data/{decision_name}/csv/rules.csv', header=0, delimiter=';')
        conditions_df = read_csv(f'../data/{decision_name}/csv/conditions.csv', header=0, delimiter=';')
        derivations_df = read_csv(f'../data/{decision_name}/csv/derivations.csv', header=0, delimiter=';')

        return cls(variables_df, rules_df, conditions_df, derivations_df)

    def update_graph(self, graph, local=False):
        self.update_graph_variables(graph, local)
        self.update_graph_rules(graph, local)
        self.update_graph_derivations(graph, local)

    def update_graph_variables(self, graph, local=False):
        for var in self.variables_df.itertuples():
            obj_name, var_name = var.trace.split(".")
            var_node = graph.nodes.match(var.type, name=var_name).where(f"(:ObjectType {{name: '{obj_name}'}})-[:has_property]->(_)").first()
            if not var_node:
                raise ValueError(f'Could not update variable node {var.name} to {var.value}.')
            if local:
                var_node['waarde'] = var.value
                graph.push(var_node)

    def update_graph_rules(self, graph, local=False):
        for rule in self.rules_df.itertuples():
            obj_name, var_name = rule.derivation_trace.split(".")
            derivation_node = graph.nodes.match('KBNode', name=var_name).where(f"(:ObjectType {{name: '{obj_name}'}})-[:has_property]->(_)").first()
            if not derivation_node:
                raise ValueError(f'No derivation node found for {var_name} of {obj_name}.')
            rule_node = graph.nodes.match('Regel', name=rule.name).where(f"(_)-[:derivation]->({derivation_node.labels} {{alef_id:'{derivation_node['alef_id']}'}})").first()
            if not rule_node:
                raise ValueError(f'No rule node found for {rule.name}.')
            
            if local:
                rule_node['waarde'] = rule.value
            rule_node['geldigheid'] = rule.validity
            rule_node['bron'] = rule.source
            graph.push(rule_node)

    def update_graph_derivations(self, graph, local=False):
        for derivation in self.derivations_df.itertuples():
            obj_name, var_name = derivation.derivation_trace.split(".")
            derivation_node = graph.nodes.match('KBNode', name=var_name).where(f"(:ObjectType {{name: '{obj_name}'}})-[:has_property]->(_)").first()
            if not derivation_node:
                raise ValueError(f'No derivation node found for {var_name} of {obj_name}.')
            rule_node = graph.nodes.match('Regel', name=derivation.rule).where(f"(_)-[:derivation]->({derivation_node.labels} {{alef_id:'{derivation_node['alef_id']}'}})").first()
            if not rule_node:
                raise ValueError(f'No rule node found for {derivation.rule}')
            

