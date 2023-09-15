# mps_explaineo

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
│   └── mps_to_graphmodel.ipynb     <-- 
└── setup.py                        
```
