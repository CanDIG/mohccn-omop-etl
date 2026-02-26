# Vocab Server Docker Setup

## Important: Required Files Not In This Repo

### Athena

In order to get this to work, you'll need a copy of the Athena vocabulary:
https://athena.ohdsi.org

You'll have to sign up and receive a private download link. The downloaded files shoulld go to the `postgres/vocab_data/` folder like so:
```
fnguyen@techna-omop:~/mohccn-omop-etl/vocabulary_server_setup$ ls postgres/vocab_data/
CONCEPT.csv  CONCEPT_ANCESTOR.csv  CONCEPT_CLASS.csv  CONCEPT_RELATIONSHIP.csv  CONCEPT_SYNONYM.csv  DOMAIN.csv  DRUG_STRENGTH.csv  RELATIONSHIP.csv  VOCABULARY.csv
```

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
