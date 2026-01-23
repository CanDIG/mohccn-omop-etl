import pandas as pd
import json
import requests.exceptions as exceptions
import os
import sys
import argparse
import settings
import requests
from generate_etl_rules import generate_etl_rules
from validate_openapi_json import validate_json
from pathlib import Path
# from clinical_etl import mohschemav3
import re

from urllib.parse import quote
from datetime import datetime, timedelta
from typing import Dict, Any, List

class MohccnToOmopTransformer:
	"""
	A class to handle the transformation of MOHCCN data to OMOP CDM format.
	
	This class provides functionality to load validation rules, ETL rules, and vocabulary mappings,
	and contains constants for various transformation operations.
	"""
	
	# Constants for transformation operations
	INSTRUCTION_FIXED_VALUE = "Fixed Value"
	INSTRUCTION_FIXED_VALUE_IF_NOT_EMPTY = "Fixed Value If Not Empty"
	INSTRUCTION_RESET_GLOBAL_VARS = "Reset Global Vars"
	INSTRUCTION_SAVE_TO_GLOBAL_VARS = "Save To Global Vars"
	INSTRUCTION_GENERATE_UNIQUE_ID = "Generate Unique ID"
	INSTRUCTION_GENERATE_UNIQUE_ID_FROM_PATH = "Generate Unique ID From Path"
	INSTRUCTION_GET_UNIQUE_ID = "Get Unique ID"
	INSTRUCTION_GET_UNIQUE_ID_NO_GLOBAL_VARS = "Get Unique ID (No Global Vars)"
	INSTRUCTION_GET_UNIQUE_ID_FROM_PATH = "Get Unique ID From Path"
	INSTRUCTION_CONCEPT_ID_BY_TERM = "Concept ID By Term"
	INSTRUCTION_COPY_VALUE = "Copy Value"
	INSTRUCTION_COPY_NODE = "Copy Node"
	INSTRUCTION_CALCULATE_YEAR_FROM_INTERVAL = "Calculate Year From Interval"
	INSTRUCTION_CALCULATE_MONTH_FROM_INTERVAL = "Calculate Month From Interval"
	INSTRUCTION_CALCULATE_DAY_FROM_INTERVAL = "Calculate Day From Interval"
	INSTRUCTION_CALCULATE_DATE_FROM_INTERVAL = "Calculate Date From Interval"
	INSTRUCTION_CALCULATE_DATE_FROM_AGE = "Calculate Date From Age"
	INSTRUCTION_CONCEPT_ID_BY_CODE = "Concept ID By Code"
	INSTRUCTION_CONCATENATE_VALUES = "Concatenate Values"
	CONCATENATE_CHAR = "|"

	REQUIREMENT_RULE_SKIP_RECORD = 'Skip Record'
	REQUIREMENT_RULE_PLACEHOLDER_PREFIX = 'Placeholder:'
	
	def __init__(self, 
				 mohccn_validation_rules_json_filename: str,
				 mohccn_to_omop_etl_rules_json_filename: str,
				 vocabulary_term_mappings_xlsx_filename: str,
				 debug_raw_json_node_paths_file: str,
				 debug_output_log_filename: str,
				 debug_omop_json_filename: str,
				 vocab_server_search_by_code_url: str):
		"""
		Initialize the MohccnToOmopTransformer with the required file paths.
		
		Args:
			mohccn_validation_rules_json_filename: Path to the validation rules JSON file
			mohccn_to_omop_etl_rules_json_filename: Path to the ETL rules JSON file
			vocabulary_term_mappings_xlsx_filename: Path to the vocabulary mappings Excel file
			debug_raw_json_node_paths_file: Path to the debug raw JSON node paths file
			debug_output_log_filename: Path to the debug output log file
			debug_omop_json_filename: Path to the debug OMOP JSON file
			vocab_server_search_by_code_url: URL of the vocabulary server search by code endpoint
		"""
		# self._mohccn_validation_rules_json_filename = mohccn_validation_rules_json_filename
		# self._mohccn_to_omop_etl_rules_json_filename = mohccn_to_omop_etl_rules_json_filename
		# self._vocabulary_term_mappings_xlsx_filename = vocabulary_term_mappings_xlsx_filename
		self._debug_raw_json_node_paths_file = debug_raw_json_node_paths_file
		self._debug_output_log_filename = debug_output_log_filename
		self._debug_omop_json_filename = debug_omop_json_filename
		self._vocab_server_search_by_code_url = vocab_server_search_by_code_url
		self._field_regex_for_integer_conversion = [
			"^[\\w\\_]+\\.[\\w\\_]+_concept_id$",
			"^person\\.year_of_birth$",
			"^person\\.month_of_birth$",
			"^person\\.day_of_birth$",
			"^episode\\.episode_number$"
		]
		self._field_regex_to_maxlength = {
			"^[\\w\\_]+\\.[\\w\\_]+_source_value$" : 50
		}
		self._duplicate_id_map_check = []

		self.log_message(f"Logging debug output to: {self._debug_output_log_filename}", True, False)

		# Clear or initialize debug output log file
		if ( self._debug_output_log_filename != "" ):
			with open(self._debug_output_log_filename, 'w', encoding='utf-8') as f:
				f.write("")

		# Initialize data containers
		self._validation_rules = {}
		self._etl_rules = {}
		self._term_to_concept_id_mappings = {}
		self._initial_global_vars = {"{siteId}" : "PM2C"}  # PM2C (UHN), BCGSC, MOH-Q
		self._global_vars = {}
		self._skipped_unique_ids = []
		self._ready_to_transform = False
		
		# Load the data files
		success1 = self._load_validation_rules(mohccn_validation_rules_json_filename)
		success2 = self._load_etl_rules(mohccn_to_omop_etl_rules_json_filename)
		success3 = self._load_vocabulary_mappings(vocabulary_term_mappings_xlsx_filename)

		self._ready_to_transform = ( success1 and success2 and success3 )

	def log_message(self, message: str, to_console: bool = True, to_file: bool = True, reset_file: bool = False):
		"""Log a message to the debug output log file."""
		if ( to_file and self._debug_output_log_filename != "" ):
			mode = 'w' if reset_file else 'a'
			with open(self._debug_output_log_filename, mode, encoding='utf-8') as f:
				f.write(f"{message}\n")
		if ( to_console ):
			print(message)
	
	def _load_validation_rules(self, mohccn_validation_rules_json_filename: str) -> bool:
		self.log_message(f"Validation rules loading: {mohccn_validation_rules_json_filename}...")
		"""Load validation rules from JSON file."""
		validation_rules_result = self.load_and_parse_json_file(mohccn_validation_rules_json_filename)
		if ( validation_rules_result != False):
			self._validation_rules = validation_rules_result
			self.log_message(f"Validation rules loaded successfully!")
			return True

		return False
	
	def _load_etl_rules(self, mohccn_to_omop_etl_rules_json_filename: str) -> bool:
		"""Load ETL rules from JSON file."""
		self.log_message(f"ETL rules loading: {mohccn_to_omop_etl_rules_json_filename}...")
		etl_rules_result = self.load_and_parse_json_file(mohccn_to_omop_etl_rules_json_filename)
		if ( etl_rules_result != False):
			self._etl_rules = etl_rules_result
			self.log_message(f"ETL rules loaded successfully!")
			return True

		return False
	
	def _load_vocabulary_mappings(self, vocabulary_term_mappings_xlsx_filename: str) -> bool:
		"""Load vocabulary mappings from Excel file."""
		try:
			# This would need to be implemented with pandas or openpyxl
			# For now, we'll just store the filename
			self.log_message(f"Vocabulary mappings loading: {vocabulary_term_mappings_xlsx_filename}")

			# Load vocabulary mappings from Excel file
			df = pd.read_excel(vocabulary_term_mappings_xlsx_filename, dtype=str)
			
			# Replace nan with empty string
			# df.fillna('', inplace=True)
			
			# Filter for rows that have a mapped value
			mapped_df = df[df['Mapped By'].notna()]
			
			# Initialize vocabulary mappings dictionary
			self._term_to_concept_id_mappings = {}
			
			# Build nested dictionary structure
			for _, row in mapped_df.iterrows():
				schema = row['Schema'].lower()
				field = row['Field'].lower()
				orig_term = row['Original Term'].lower()
				concept_id = row['Concept ID']
				
				# Create nested dictionaries if they don't exist
				if schema not in self._term_to_concept_id_mappings:
					self._term_to_concept_id_mappings[schema] = {}
				if field not in self._term_to_concept_id_mappings[schema]:
					self._term_to_concept_id_mappings[schema][field] = {}
					
				# Add mapping
				self._term_to_concept_id_mappings[schema][field][orig_term] = concept_id
		except Exception as e:
			self.log_message(f"Error loading vocabulary mappings: {e}")
			return False
		self.log_message(f"Vocabulary mappings loaded successfully!")
		return True
	
	def load_and_parse_json_file(self, file_path: str) -> Dict[str, Any] or bool:
		"""
		Load and parse the JSON file.
		
		Args:
			file_path: Path to the JSON file
		
		Returns:
			Parsed JSON data or False if error
		"""
		try:
			with open(file_path, 'r', encoding='utf-8') as f:
				data = json.load(f)
			return data
		except FileNotFoundError:
			self.log_message(f"Error: File '{file_path}' not found.")
			return False
		except json.JSONDecodeError as e:
			self.log_message(f"Error: Invalid JSON in file '{file_path}': {e}")
			return False
		except Exception as e:
			self.log_message(f"Error loading file '{file_path}': {e}")
			return False
	
		
	def _validate_source_field(self, data: Dict, source_schema: str, source_field: str):
		"""
		Validate the source field.
		"""
		print (f"{source_schema} {source_field}")
		test = self._validation_rules[source_schema][source_field] if source_schema in self._validation_rules and source_field in self._validation_rules[source_schema] else {}
		print(test)
		print(f"Type of test: {type(test)}")
		print(test["requiredAlways"])
		sys.exit()
		# if ( source_field in data):
		#	 print(data[source_field])
		# else:
		#	 print(f"Source field {source_field} not found in data")
		#	 sys.exit()

	def _process_omop_table(self, omop_records: List[Dict], current_path: str, data_group: str, target_table: str, data: Dict, meta_data: List):
		omop_data = {
			"omop_table" : target_table,
			"skip_errors" : [],
			"omop_record" : {}
			}


		# Load default values
		default_values = self._etl_rules["$"]["Default Values"]
		if target_table in default_values:
			default_value_meta_data = default_values[target_table]
			for instructions in default_value_meta_data:
				self._load_value_for_instruction(target_table, omop_data["omop_record"], omop_data["skip_errors"], current_path, data_group, data, instructions)


		current_unique_id = None
		for instructions in meta_data:
			value = self._load_value_for_instruction(target_table, omop_data["omop_record"], omop_data["skip_errors"], current_path, data_group, data, instructions)

			# Store all generated unique IDs
			if (instructions["Instruction"] in [self.INSTRUCTION_GENERATE_UNIQUE_ID, self.INSTRUCTION_GENERATE_UNIQUE_ID_FROM_PATH]):
				current_unique_id = value
				if ( current_unique_id in self._duplicate_id_map_check ):
					self.log_message(f"Duplicate ID map found: {current_unique_id}")
					pass
				else:
					self._duplicate_id_map_check.append(current_unique_id)


		if len(omop_data["skip_errors"]) != 0 and current_unique_id:
			# print(omop_data["skip_errors"])
			# print(current_unique_id)

			# Track unique IDs that are skipped
			if ( current_unique_id not in self._skipped_unique_ids ):
				# print (f"Skipping OMOP record with unique_id: {current_unique_id}")
				self._skipped_unique_ids.append(current_unique_id)

		# print(data)
		# print(omop_data)
		# print("")
		# sys.exit()
		omop_records.append(omop_data)

	def _load_value_for_instruction(self, target_table: str, target_dict: Dict, skip_errors: List, current_path: str, data_group: str, data: Dict, instructions: Dict, allow_empty_string: bool = False) -> str:
		target_field = instructions["Target Field"]
		instruction = instructions["Instruction"]
		value = instructions["Value"] if "Value" in instructions else ""
		vocab = instructions["Vocab"] if "Vocab" in instructions else ""
		requirement_rule = instructions["Requirement Rule"] if "Requirement Rule" in instructions else ""
		source_schema = instructions["MOHCCN Source Schema"] if "MOHCCN Source Schema" in instructions else ""
		source_field = instructions["Source Field"] if "Source Field" in instructions else ""
		source_schema_and_field = f"{source_schema}.{source_field}"
		unique_id_instructions = [self.INSTRUCTION_GENERATE_UNIQUE_ID, self.INSTRUCTION_GENERATE_UNIQUE_ID_FROM_PATH,
			self.INSTRUCTION_GET_UNIQUE_ID, self.INSTRUCTION_GET_UNIQUE_ID_FROM_PATH, self.INSTRUCTION_GET_UNIQUE_ID_NO_GLOBAL_VARS]
		

		# if ( data_group == "OMOP Treatment Episode Procedure Occurrence" ):
		# 	print(self._global_vars)
		# 	print(f"{data_group} {target_field} {instruction} {value} {vocab} {source_schema} {source_field} = {data[source_field] if source_field in data else ""}")
		# print(f"{var_name} {instruction} {value} {vocab} {source_schema} {source_field} = {data[source_field] if source_field in data else ""}")

		final_value = ""
		if ( instruction == self.INSTRUCTION_FIXED_VALUE):
			final_value = value
		elif ( instruction == self.INSTRUCTION_FIXED_VALUE_IF_NOT_EMPTY):
			if (source_field in data and data[source_field] != ""):
				final_value = value
		elif ( instruction == self.INSTRUCTION_RESET_GLOBAL_VARS):
			
			self._global_vars = self._initial_global_vars.copy()
		elif ( instruction == self.INSTRUCTION_SAVE_TO_GLOBAL_VARS):
			# Overwrite target_field to include schema
			target_field = f"{{{source_schema_and_field}}}"
			final_value = data[source_field] if source_field in data else ""
			# print(self._global_vars)
		elif ( instruction == self.INSTRUCTION_COPY_NODE):
			if ( source_schema != "N/A"):
				if ( source_field == "N/A"):
					self.log_message(f"Source field is N/A for {instructions}")
					sys.exit()
				# print(source_schema)
				final_value = data[source_field] if source_field in data else ""
			else:
				final_value = data
		elif ( instruction == self.INSTRUCTION_COPY_VALUE):
			# print(f"{source_schema} {source_field}")
			# Does source field exist in data?
			# self._validate_source_field(data, source_schema, source_field)

			if ( source_schema != "N/A"):
				if ( source_field == "N/A"):
					self.log_message(f"Source field is N/A for {instructions}")
					sys.exit()
				# print(source_schema)
				final_value = data[source_field] if source_field in data else ""
			else:
				final_value = self._replace_global_var_name_with_value(value)
		elif ( instruction in unique_id_instructions):
			# If source_field does not exist in data, check global vars
			source_id = self._global_vars["{source_id}"]
			source_desc = source_schema_and_field
			# When generating unique ID, use the DHDP Data Group, if getting unique ID, use the Value provided
			target_desc = data_group if (instruction in [self.INSTRUCTION_GENERATE_UNIQUE_ID, self.INSTRUCTION_GENERATE_UNIQUE_ID_FROM_PATH]) else value
			if ( source_field not in data):
				global_var_name = f"{{{source_schema_and_field}}}"
				if ( global_var_name in self._global_vars and instruction not in [self.INSTRUCTION_GET_UNIQUE_ID_NO_GLOBAL_VARS] ):
					final_value = {
						"type" : "id_map",
						"source_system": source_id,
						"source_value": self._global_vars[global_var_name],
						"source_desc": source_desc,
						"target_desc": target_desc
					}
			else:
				# final_value = f"{data[source_field]}|{source_field}|{data_group}"
				final_value = {
					"type" : "id_map",
					"source_system": source_id,
					"source_value": data[source_field],
					"source_desc": source_desc,
					"target_desc": target_desc
				}
				
			if ( isinstance(final_value, dict) and instruction in [self.INSTRUCTION_GENERATE_UNIQUE_ID_FROM_PATH, self.INSTRUCTION_GET_UNIQUE_ID_FROM_PATH]):
				final_value["source_value"] = f"{final_value['source_value']}+{current_path}"
				final_value["source_desc"] = f"{final_value['source_desc']}+{self._sanitize_path(current_path)}"

			# For get unique ID, check if is in the skipped unique ids list
			if ( isinstance(final_value, dict) and instruction in [self.INSTRUCTION_GET_UNIQUE_ID, self.INSTRUCTION_GET_UNIQUE_ID_FROM_PATH] and final_value in self._skipped_unique_ids):
				self.log_message(f"Skipped OMOP record for '{target_table}' referencing skipped unique_id: {final_value}")
				skip_errors.append(f"Skipped OMOP record referencing skipped unique_id: {final_value}")

		elif ( instruction == self.INSTRUCTION_CONCEPT_ID_BY_TERM):
			final_value = self._get_concept_id_by_term(source_schema, source_field, data, value)
		elif ( instruction == self.INSTRUCTION_CALCULATE_YEAR_FROM_INTERVAL):
			final_value = self._calculate_year_from_interval(source_field, data)
		elif ( instruction == self.INSTRUCTION_CALCULATE_MONTH_FROM_INTERVAL):
			final_value = self._calculate_month_from_interval(source_field, data)
		elif ( instruction == self.INSTRUCTION_CALCULATE_DAY_FROM_INTERVAL):
			final_value = self._calculate_day_from_interval(source_field, data)
		elif ( instruction == self.INSTRUCTION_CALCULATE_DATE_FROM_INTERVAL):
			new_date = self._calculate_date_from_interval(source_field, data, value)
			if ( new_date and isinstance(new_date, datetime)):
				final_value = new_date.strftime('%Y-%m-%d')			
		elif ( instruction == self.INSTRUCTION_CALCULATE_DATE_FROM_AGE):
			new_date = self._calculate_day_from_age(source_field, data)
			if ( new_date and isinstance(new_date, datetime)):
				final_value = new_date.strftime('%Y-%m-%d')			
		elif ( instruction == self.INSTRUCTION_CONCEPT_ID_BY_CODE):
			final_value = self._get_concept_id_by_code(vocab, source_field, data)
		elif ( instruction == self.INSTRUCTION_CONCATENATE_VALUES):
			# Split source field on comma if present
			if "," in source_field:
				fields = [field.strip() for field in source_field.split(",")]
				values = [data[field] for field in fields if field in data]
				final_value = self.CONCATENATE_CHAR.join(values)
			elif ( source_field in data):
				final_value = self.CONCATENATE_CHAR.join(data[source_field])
			# sys.exit()
		else:
			self.log_message(f"Unknown instruction: {instruction}")
			sys.exit()
		
		# If the instruction is optional and the final value is empty, don't add it to the target dictionary
		# Handle placeholder requirement rules
		if ( final_value == "" and requirement_rule and requirement_rule.startswith(self.REQUIREMENT_RULE_PLACEHOLDER_PREFIX) ):
			# Extract placeholder value after prefix
			final_value = self._replace_global_var_name_with_value(requirement_rule[len(self.REQUIREMENT_RULE_PLACEHOLDER_PREFIX):].strip())
		elif ( final_value == "" and requirement_rule == self.REQUIREMENT_RULE_SKIP_RECORD ):
			skip_errors.append(f"Data for '{source_field}' is missing for '{data_group}' / '{instruction}' at {current_path}")
		
		if ( final_value != "" or allow_empty_string ):
			target_table_and_field = f"{target_table}.{target_field}"

			# Cycle through the field regex to maxlength dictionary and if the field matches, check if the final value is longer than the maxlength
			for regex, maxlength in self._field_regex_to_maxlength.items():
				if re.match(regex, target_table_and_field) and len(final_value) > maxlength:
					self.log_message(f"Truncating {target_table_and_field} '{final_value}' to {maxlength} chars", False)
					final_value = final_value[:maxlength]
					break

			# Cycle through the regexes and convert the field to an integer if it matches
			for regex in self._field_regex_for_integer_conversion:
				if re.match(regex, target_table_and_field):
					try:
						self.log_message(f"Converting {target_table_and_field} '{final_value}' to int", False)
						final_value = int(final_value)
						break
					except (ValueError, TypeError):
						pass  # If conversion fails, leave as is
					break
			target_dict[target_field] = final_value
			
		return final_value

	def _calculate_year_from_interval(self, source_field: str, data: Dict) -> str:
		new_date = self._calculate_date_from_interval(source_field, data, "")
		if ( new_date and isinstance(new_date, datetime)):
			return str(new_date.year)
		else:
			return ""

	def _calculate_month_from_interval(self, source_field: str, data: Dict) -> str:
		new_date = self._calculate_date_from_interval(source_field, data, "")
		if ( new_date and isinstance(new_date, datetime)):
			return str(new_date.month)
		else:
			return ""

	def _calculate_day_from_interval(self, source_field: str, data: Dict) -> str:
		new_date = self._calculate_date_from_interval(source_field, data, "")
		if ( new_date and isinstance(new_date, datetime)):
			return str(new_date.day)
		else:
			return ""
		
	def _calculate_day_from_age(self, source_field: str, data: Dict) -> str:
		dob_interval = self._global_vars["{Donor.date_of_birth}"] if "{Donor.date_of_birth}" in self._global_vars else ""
		# dob_interval = self._global_vars["{Donor.date_of_birth}"]
		if ( dob_interval == ""):
			self.log_message(f"Info: Date of birth interval not found in global vars", False)
			return ""
		age = int(data[source_field]) if source_field in data else 0

		# Convert dob_interval to incorporate age in years as the delta, and overwrite value in data
		age_interval = {
			"day_interval": int(dob_interval["day_interval"]) + age * 365,
			"month_interval": int(dob_interval["month_interval"]) + age * 12}
		data[source_field] = age_interval

		new_date = self._calculate_date_from_interval(source_field, data, "")
		if ( new_date and isinstance(new_date, datetime)):
			return new_date
		else:
			return ""
		
	def _calculate_date_from_interval(self, source_field: str, data: Dict, value: str) -> datetime:
		if ( source_field == "N/A"):
			json_interval = self._replace_global_var_name_with_value(value)
		elif ( source_field not in data):
			# print(f"Source field {source_field} not found in data")
			return ""
		else:
			json_interval = data[source_field]

		# Handle case where json_interval is a string
		if isinstance(json_interval, str):
			return ""

		date_resolution = self._global_vars["{Donor.date_resolution}"]

		fixed_date = self._global_vars["{fixed_date}"]
		# Convert fixed_date string to datetime object
		try:
			fixed_date_obj = datetime.strptime(fixed_date, '%Y-%m-%d')
		except ValueError:
			self.log_message(f"Error: Date format '%Y-%m-%d' required for fixed_date: {fixed_date}")
			sys.exit()

		if ( date_resolution == "day"):
			# print(json_interval["day_interval"])
			# Calculate new date by adding day_interval days to fixed_date
			try:
				day_interval = int(json_interval["day_interval"])
				new_date = fixed_date_obj + timedelta(days=day_interval)
				return new_date
			except (ValueError, KeyError) as e:
				self.log_message(f"Error calculating date from day interval: {e}")
				return False
		elif ( date_resolution == "month"):
			# print(json_interval["month_interval"])
			try:
				month_interval = int(json_interval["month_interval"])
				new_date = fixed_date_obj + timedelta(months=month_interval)
				return new_date
			except (ValueError, KeyError) as e:
				self.log_message(f"Error calculating date from month interval: {e}")
				return False

	def _get_concept_id_by_code(self, vocab: str, source_field: str, data: Dict) -> str:
		"""
		Get the concept ID by code.
		"""
		initial_value = data[source_field] if source_field in data else ""
		# print(f"Initial value for code map: {initial_value}")

		if ( initial_value == ""):
			return ""

		params = {
			"code": initial_value,
			"vocab": self._replace_global_var_name_with_value(vocab)
		}

		if ( self._vocab_server_search_by_code_url == ""):
			self.log_message(f"Error: Vocabulary server search by code URL is not set")
			return ""

		base_url = self._vocab_server_search_by_code_url
		query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
		url = f"{base_url}?{query_string}"
		# print(url)
		# sys.exit()
	
		self.log_message(f"Searching for concept ID by code: {url}", False, True, False)
		try:
			# Make the API request
			response = requests.get(url, timeout=30)
			response.raise_for_status()
			
			# Parse JSON response
			data = response.json()
			if data and len(data) > 0:
				first_key = next(iter(data))

				# Get the first JSON object
				first_result = data[first_key]
				return first_result.get('conceptId', '')
			else:
				return "0"
			
		# except requests.exceptions.RequestException as e:
		#	 print(f"Error processing row {row_count}: {e}")
		#	 continue
		except json.JSONDecodeError as e:
			self.log_message(f"JSON parsing error: {e}")
			return ""
		except exceptions.HTTPError as e:
			self.log_message(f"HTTP error {e.response.status_code} for URL: {url}")
			return ""
		except Exception as e:
			# traceback.print_exc()
			self.log_message(f"Unexpected error: {e}")
			return ""
			# print(f"Unexpected error processing row {row_count}: {e}")


	def _get_concept_id_by_term(self, source_schema: str, source_field: str, data: Dict, value: str) -> str:
		"""
		Get the concept ID by term.
		"""
		if ( source_field == "N/A"):
			initial_value = self._replace_global_var_name_with_value(value)
			# print(data)
			# print(type(data))
			# sys.exit()
		else:
			initial_value = data[source_field] if source_field in data else ""

		possible_terms = self._term_to_concept_id_mappings[source_schema.lower()][source_field.lower()] if source_schema.lower() in self._term_to_concept_id_mappings and source_field.lower() in self._term_to_concept_id_mappings[source_schema.lower()] else {}

		# print(f"Initial value for term map: {initial_value}")
		if ( initial_value == "" ):
			final_value = ""
		elif ( initial_value != "" and initial_value.lower() in possible_terms.keys()):
			final_value = possible_terms[initial_value.lower()]
		else:
			final_value = "0"
		
		# print(final_value)   
		# sys.exit()
		return final_value

	def _process_global_vars(self, current_path: str, data_group: str, data: Dict, meta_data: List):
		"""
		Process the global variables.
		"""
		# print(data)
		# print("")
		# print(meta_data)
		# print("")
		for item in meta_data:
			self._load_value_for_instruction("_global_vars", self._global_vars, [], current_path, data_group, data, item, True)

			# print(self._global_vars)

	def _replace_global_var_name_with_value(self, var: str) -> str:
		"""
		Check if a string contains any global variable names from self._global_vars.
		
		Args:
			var_name: The string to check
			
		Returns:
			bool: True if var_name contains any global variable names, False otherwise
		"""
		for global_var_name in self._global_vars.keys():
			if global_var_name in var:
				if isinstance(self._global_vars[global_var_name], dict):
					# Convert dict to string and back to handle dict values
					dict_str = json.dumps(self._global_vars[global_var_name])
					var = json.loads(var.replace(global_var_name, dict_str))
				else:
					var = var.replace(global_var_name, self._global_vars[global_var_name])
		return var

	def traverse_nodes(self, results_by_json_path: Dict, data: Any, current_path: str, paths: List[str] = None) -> List[str]:
		"""
		Recursively traverse through all nodes in the JSON data and build paths.
		
		Args:
			data: The current data node (dict, list, or primitive value)
			current_path: The current path string
			paths: List to store all discovered paths
		
		Returns:
			List of all node paths
		"""

		if paths is None:
			paths = []
		
		if isinstance(data, dict):
			""" 
			Process dictionary node
			"""
			
			# print(f"O: {current_path}")
			sanitized_path = self._sanitize_path(current_path)
			if ( sanitized_path in self._etl_rules):
				etl_rules = self._etl_rules[sanitized_path]

				# Initialize array for json path
				if ( current_path not in results_by_json_path ):
					results_by_json_path[current_path] = []
				
				for data_group, target_tables in etl_rules.items():
					# Skip Default Values
					if ( data_group == "Default Values"):
						continue

					for target_table, meta_data in target_tables.items():
						# First process target_table "_global_vars"
						if ( target_table == "_global_vars"):
							self._process_global_vars(current_path, data_group, data, meta_data)
						else:
							self._process_omop_table(results_by_json_path[current_path], current_path, data_group, target_table, data, meta_data)
							# if ( target_table == "dataset"):
								# print(f"Dataset: {results_by_json_path[current_path]}")
								# sys.exit()



					# elif ( data_group == "_global_vars"):



			# For dictionaries, traverse each key-value pair
			for key, value in data.items():
				# Build the path for this node
				node_path = f"{current_path}.{key}" if current_path else key
				paths.append(node_path)
				
				# Recursively traverse child nodes
				self.traverse_nodes(results_by_json_path, value, node_path, paths)
				
		elif isinstance(data, list):
			# For lists, traverse each item with index
			for i, item in enumerate(data):


				# Build the path for this node
				node_path = f"{current_path}[{i}]"
				paths.append(node_path)
				
				# Recursively traverse child nodes
				self.traverse_nodes(results_by_json_path, item, node_path, paths)
		elif isinstance(data, (str, int, float, bool)):
			# Check if sanitized path is in ETL rules for primitive values, e.g. treatment_type
			sanitized_path = self._sanitize_path(current_path)
			if ( sanitized_path in self._etl_rules):
				etl_rules = self._etl_rules[sanitized_path]
				# print(current_path)

				# Initialize array for json path
				if ( current_path not in results_by_json_path ):
					results_by_json_path[current_path] = []
				# print(etl_rules)
				for data_group, target_tables in etl_rules.items():
					# Skip Default Values
					if ( data_group == "Default Values"):
						continue

					for target_table, meta_data in target_tables.items():
						# First process target_table "_global_vars"
						if ( target_table == "_global_vars"):
							self._process_global_vars(current_path, data_group, data, meta_data)
						else:
							self._process_omop_table(results_by_json_path[current_path], current_path, data_group, target_table, data, meta_data)


			# Primitive value, nothing to traverse further
			
		# For primitive values (strings, numbers, booleans, None), we don't traverse further
		# The path was already added when we encountered the parent
		
		return paths
	def _sanitize_path(self, path: str) -> str:
		"""
		Sanitize the path by removing any invalid characters.
		"""
		# Replace array indices with empty brackets using regex
		import re
		return re.sub(r'\[\d+\]', '[]', path)

	def transform_mohccn_to_omop(self, raw_data: Dict[str, Any], output_json_filename: str) -> Dict[str, Any]:
		"""
		Transform MOHCCN data to OMOP CDM format.
		
		Args:
			raw_data: Raw data to transform
		"""

		if ( not self._ready_to_transform ):
			self.log_message("Error: Not ready to transform. Validation rules, ETL rules, or vocabulary mappings not loaded successfully.")
			return {}

		results_by_json_path = {}
		raw_data_paths = self.traverse_nodes(results_by_json_path, raw_data, "$")
		self.log_message(f"Found {len(raw_data_paths)} total nodes in source JSON")

		# Save raw data paths to a file
		if ( self._debug_raw_json_node_paths_file != "" ):
			with open(self._debug_raw_json_node_paths_file, 'w', encoding='utf-8') as f:
				for i, path in enumerate(raw_data_paths, 1):
					f.write(f"{i:4d}. {path}\n")
			self.log_message(f"Source JSON node paths saved to: {self._debug_raw_json_node_paths_file}")

		# Save immediate transformation results to file
		if ( self._debug_omop_json_filename != "" ):
			with open(self._debug_omop_json_filename, 'w', encoding='utf-8') as f:
				f.write(json.dumps(results_by_json_path, indent='\t'))
			self.log_message(f"Full OMOP transformation JSON saved to: {self._debug_omop_json_filename}")


		self.log_message("Converting full OMOP transformation JSON to final nested JSON format...")
		current_donor_id = ""
		dataset_source_value_to_dataset_array_index_map = {}
		current_donor_array_index = current_dataset_array_index = 0
		results_by_datasets = {"datasets" : []}
		for json_path, omop_records in results_by_json_path.items():
			# print(json_path)
			for omop_record in omop_records:
				omop_table_name = omop_record["omop_table"]
				skip_errors = omop_record["skip_errors"]
				if ( omop_table_name == "dataset"):
					current_dataset_id = omop_record["omop_record"]["id"]
					if ( current_dataset_id not in dataset_source_value_to_dataset_array_index_map ):
						results_by_datasets["datasets"].append({
							"id": current_dataset_id,
							"linked_records" : []
						})
						current_dataset_array_index = len(results_by_datasets["datasets"])-1
						dataset_source_value_to_dataset_array_index_map[current_dataset_id] = current_dataset_array_index
					else:
						current_dataset_array_index = dataset_source_value_to_dataset_array_index_map[current_dataset_id]
				elif ( omop_table_name == "person"):
					if ( current_donor_id != omop_record["omop_record"]["person_id"] ):
						current_donor_id = omop_record["omop_record"]["person_id"]
						new_record = {omop_table_name: omop_record["omop_record"].copy()}
						del new_record[omop_table_name]["person_id"]
						results_by_datasets["datasets"][current_dataset_array_index]["linked_records"].append({
							"person": new_record["person"],
							"linked_records": []
						})
						current_donor_array_index = len(results_by_datasets["datasets"][current_dataset_array_index]["linked_records"])-1
				elif ( len(skip_errors) == 0 ):
					new_record = {omop_table_name: omop_record["omop_record"].copy()}

					# If record has person_id, can remove since now nested by person
					if ( "person_id" in new_record[omop_table_name] ):
						del new_record[omop_table_name]["person_id"]

					# Cycle through each attribute in the new record and if it is a dictionary with attribute type of id_map, then
					# convert to source_value~target_desc format
					for attribute, value in new_record[omop_table_name].items():
						if ( isinstance(value, dict) and value.get("type") == "id_map" ):
							new_record[omop_table_name][attribute] = new_record[omop_table_name][attribute]["source_value"] + "~" + new_record[omop_table_name][attribute]["target_desc"].replace(" ", "_")

					results_by_datasets["datasets"][current_dataset_array_index]["linked_records"][current_donor_array_index]["linked_records"].append(new_record)

			# print(results_by_donor["datasets"])
			# print(current_donor_array_index)
			# if ( current_donor_id != "" and current_dataset_id != "" ):
			# 	results_by_datasets["datasets"][current_donor_array_index][json_path] = omop_records
			# 	results_by_donor["data"][current_donor_json_path][json_path] = omop_record


		# Save OMOP records to JSON file
		try:
			with open(output_json_filename, 'w', encoding='utf-8') as f:
				json.dump(results_by_datasets, f, indent='\t')
			self.log_message(f"Final OMOP JSON saved to: {output_json_filename}")
		except Exception as e:
			self.log_message(f"Error saving OMOP JSON to file: {e}")
	
		return results_by_datasets



def main():
	"""
	Main function to instantiate the transformer class and demonstrate its usage.
	"""
	# Parse command line arguments
	parser = argparse.ArgumentParser(description='Transform MOHCCN data to OMOP CDM format')
	parser.add_argument('--input_mohccn_json_file', '-i', required=True, type=str, nargs='?', 
	                    help='Path to source MOHCCN JSON file for transformation to OMOP CDM')
	parser.add_argument('--output_final_json_file', '-o', type=str, nargs='?', default='output_omop_data.json', 
	                    help='Path to output JSON file for CanDIG ingestion (default: output_omop_data.json)')
	parser.add_argument('--debug_output_log_file', type=str, default='', 
	                    help='Optional path to a log file for logging transformation process')
	parser.add_argument('--debug_raw_json_node_paths_file', type=str, default='', 
	                    help='Optional path to a log file for all node paths in transfromation')
	parser.add_argument('--debug_omop_json_file', type=str, default='', 
	                    help='Optional path to a JSON file with full debugging info for transformation process')
	parser.add_argument('--debug_omop_validation_issues_csv_file', type=str, default='', 
	                    help='Optional path to a CSV file with schema validation results')
	
	
	args = parser.parse_args()
	
	# Validate input file exists
	if not os.path.exists(args.input_mohccn_json_file):
		print(f"Error: Input file '{args.input_mohccn_json_file}' not found.")
		sys.exit(1)



	try:
		generate_etl_rules()
	except Exception as e:
		print(f"Error generating ETL rules: {e}")
		sys.exit(1)

	# Instantiate the transformer class
	transformer = MohccnToOmopTransformer(
		mohccn_validation_rules_json_filename=settings.GENERATED_VALIDATION_RULES_JSON_FILE_NAME,
		mohccn_to_omop_etl_rules_json_filename=settings.GENERATED_MOHCCN_TO_OMOP_ETL_SETTINGS_JSON_FILE_NAME,
		vocabulary_term_mappings_xlsx_filename=settings.EXISTING_MAPPED_VOCAB_XLSX_FILE_NAME,
		debug_raw_json_node_paths_file=args.debug_raw_json_node_paths_file,
		debug_output_log_filename=args.debug_output_log_file,
		debug_omop_json_filename=args.debug_omop_json_file,
		vocab_server_search_by_code_url=settings.VOCAB_SERVER_SEARCH_BY_CODE_URL
	)

	start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	transformer.log_message(f"Transformation process started at: {start_time}", True, True, True)
	transformer.log_message(f"Input MOHCCN JSON file: {args.input_mohccn_json_file}")
	transformer.log_message(f"Output OMOP JSON file: {args.output_final_json_file}")

	
	# Load the raw data map JSON using the transformer
	raw_data = transformer.load_and_parse_json_file(args.input_mohccn_json_file)

	# katsu_schema = "https://raw.githubusercontent.com/CanDIG/katsu/stable/chord_metadata_service/mohpackets/docs/schemas/schema.yml"

	# schema = mohschemav3.MoHSchemaV3(katsu_schema)

	# schema.validate_ingest_map(raw_data)

	# if schema.validation_errors and schema.validation_errors.length > 0:
	# 	print("\nValidation errors found:")
	# 	for error in schema.validation_errors:
	# 		print(f"- {error}")
	# 	raise ValueError("Data validation failed. Please fix validation errors before proceeding.")

	transformed_data = transformer.transform_mohccn_to_omop(raw_data, args.output_final_json_file)

	if ( args.debug_omop_validation_issues_csv_file != "" ):
		transformer.log_message(f"Validating '{args.output_final_json_file}' against OpenAPI schema '{settings.CANDIG_API_SCHEMA_YML_URL}'...")
		errors, error_type_counts = validate_json(
			settings.CANDIG_API_SCHEMA_YML_URL, args.output_final_json_file, args.debug_omop_validation_issues_csv_file, "IngestOmopDatasets"
		)
		if ( len(errors) > 0 ):
			transformer.log_message(f"WARNING: {len(errors)} schema validation issue(s) found, saved to {args.debug_omop_validation_issues_csv_file}.")
		else:
			transformer.log_message(f"No schema validation issues found.")


	end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
	transformer.log_message(f"Transformation process completed at: {end_time}")

if __name__ == "__main__":
	main()
