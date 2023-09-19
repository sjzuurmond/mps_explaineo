**Explaineo Package Overview**

MPS_explaineo is a Python package designed to enhance the understanding of rule-based decision-making systems modelled through the ALEF-tool, which is based on JetBrains MPS. By leveraging the power of Neo4j, mps models can be visualised and questioned using the interactive Neo4j Bloom application.

**Key Modules:**
1. **`decision_method.py`**
   - This module imports decision method data from the MPS models. It acts as a bridge between the rule-based decision-making system and the explanation generation process, providing the necessary input data.

2. **`explanation_method.py`**
   - The heart of Explaineo, this module is responsible for generating explanations. It takes the content of the MPS models and transforms it into more interpretable graphs that can be questioned and visualised using python notebooks and the Neo4j Bloom application. 

3. **`html_csv_import.py`**
   - This module is responsible for retrieving additional data from HTML and CSV files, specifically required for the case-study conducted in the associated research.

4. **`knowledge_base.py`**
   - This module is essential for creating a knowledge base from the imported MPS models. It establishes the foundational structure and relationships within Neo4j, enabling the explanation generation process to access and organise the information needed for generating explanations.

**How It Works:**

MPS_explaineo follows a structured process:
1. Decision method data is imported using `decision_method.py`, providing the core information about the rule-based decision-making system.

2. `knowledge_base.py` creates a knowledge base within Neo4j, organising the imported data into a format that can be used to generate explanations.

3. `explanation_method.py` takes this organised data and generates explanations. These explanations can be accessed and used through notebooks and Bloom to interpret the decision-making system effectively.

4. Optionally, `html_csv_import.py` can be used to retrieve additional data from external sources, specifically required for the case-study conducted in the associated research. 

By following this process, mps_explaineo empowers users to gain valuable insights into complex rule-based decision-making systems, making them more transparent and interpretable.

## Project Structure

MPS_explaineo's project structure is organised as follows:

```
├── README.md                       <-- this readme file
├── data                            <-- input data
│   └── belastingrente              <-- name of service
│       ├── models                  <-- language models of service
│       │   ├── gegevens.mps        <-- mps of data model
│       │   ├── regels.mps          <-- mps of rulemodel
│       │   ├── services.mps        <-- mps of servicemodel
│       └── csv                     <-- data for instances
│       ...
├── mps_explaineo                   <-- explanation method package
│   ├── __init__.py                 
│   ├── decision_method.py          <-- imports the decision method data from mps-models
│   ├── explanation_method.py       <-- generates explanations
│   ├── html_csv_import.py          <-- retrieve additional data from html and csv files
│   └── knowledge_base.py           <-- create knowledge base from imported mps-models
├── notebooks                       <-- notebooks for ad-hoc analysis
│   └── explanation_example.ipynb   <-- example of explanation aiding the research
└── setup.py                        
```

## Getting Started

To start using Explaineo and generate human-centerd explanations for your rule-based decision-making systems, follow these steps:

1. Install Explaineo by running the following command: pip install mps_explaineo

2. Explore the example provided in the `notebooks/explanation_example.ipynb` notebook to understand how to use Explaineo with ALEF models. This example demonstrates the package's capabilities and provides insights into generating explanations.

3. If you're working with non-ALEF models, you'll need to modify and adapt the package to your specific needs. Start by understanding how your decision system relates to the contents within `decision_method.py`. This module defines data classes and methods for parsing and representing decision methods, and adapting it to your models will be a good starting point.

- **Note**: Non-ALEF models may have different data structures and requirements. You may need to customise the parsing and representation logic in `decision_method.py` to suit your specific decision-making system.

4. After adapting the package to your needs, you can use the `mps_explaineo` module to generate explanations for your rule-based decision-making system effectively.

Remember that mps_explaineo is a tool that can be tailored to various rule-based systems and target audiences. Modifying it to fit your specific use case will enable you to gain valuable insights and enhance transparency in your decision-making processes.


