# Vocab Server Docker Setup

## Important: Required Files Not In This Repo

### Athena

In order to get this to work, you'll need a copy of the Athena vocabulary. Go to https://athena.ohdsi.org/vocabulary/list and download the following vocabs

```
141	CDM 5	Cancer Modifier	Diagnostic Modifiers of Cancer (OMOP)
138	CDM 5	NCIt	NCI Thesaurus (National Cancer Institute)
118	CDM 5	NAACCR	Data Standards & Data Dictionary Volume II (NAACCR)
116	CDM 5	Supplier	OMOP Supplier
115	CDM 5	Provider	OMOP Provider
111	CDM 5	Episode Type	OMOP Episode Type
90	CDM 5	ICDO3	International Classification of Diseases for Oncology, Third Edition (WHO)
87	CDM 5	Specimen Type	OMOP Specimen Type
82	CDM 5	RxNorm Extension	OMOP RxNorm Extension
44	CDM 5	Ethnicity	OMOP Ethnicity
35	CDM 5	ICD10PCS	ICD-10 Procedure Coding System (CMS)
34	CDM 5	ICD10	International Classification of Diseases, Tenth Revision (WHO)
12	CDM 5	Gender	OMOP Gender
8	CDM 5	RxNorm	RxNorm (NLM)
6	CDM 5	LOINC	Logical Observation Identifiers Names and Codes (Regenstrief Institute)
3	CDM 5	ICD9Proc	International Classification of Diseases, Ninth Revision, Clinical Modification, Volume 3 (NCHS)
2	CDM 5	ICD9CM	International Classification of Diseases, Ninth Revision, Clinical Modification, Volume 1 and 2 (NCHS)
1	CDM 5	SNOMED	Systematic Nomenclature of Medicine - Clinical Terms (IHTSDO)
```

The downloaded files shoulld go to the `postgres/vocab_data/` folder like so:
```
fnguyen@techna-omop:~/mohccn-omop-etl/vocabulary_server_setup$ ls postgres/vocab_data/
CONCEPT.csv  CONCEPT_ANCESTOR.csv  CONCEPT_CLASS.csv  CONCEPT_RELATIONSHIP.csv  CONCEPT_SYNONYM.csv  DOMAIN.csv  DRUG_STRENGTH.csv  RELATIONSHIP.csv  VOCABULARY.csv
```

Download the DDL 5.4 from https://github.com/OHDSI/CommonDataModel, put the sql files into ddl folder

Run db_setup.sh script, remember to set the default admin user and password

### Solr postgres JDBC driver
The adaptor for Solr to access Postgres can be obtained from:
https://jdbc.postgresql.org/download/

The downloaded .jar should go into the `solr/` folder like so:
```
fnguyen@techna-omop:~/mohccn-omop-etl/vocabulary_server_setup$ ls solr/
docker-compose.yml  docker-entrypoint.sh  postgresql-42.7.5.jar  solr
```

### Vocab Server
The server GitHub is located at:
https://collaborate.uhnresearch.ca/stash/scm/hir/dhdp-vocab-search.git

You'll need a copy of it in the php/html/dhdp-vocab-search directory. Since this is an internal UHN Git, it has not been added as a submodule

## Starting Up The Docker Containers

Once all of the above steps are complete, you can set up each container with the following:
```
docker compose -f ./docker-compose.yml -f postgres/docker-compose.yml up -d
docker compose -f ./docker-compose.yml -f php/docker-compose.yml up -d
docker compose -f ./docker-compose.yml -f solr/docker-compose.yml up -d
```
