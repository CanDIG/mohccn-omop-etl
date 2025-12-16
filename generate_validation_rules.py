import pandas as pd
import json
import re
import sys
import settings

def load_map_generation_settings():

	"""Load the map generation settings JSON file."""
	with open(settings.GENERATION_SETTINGS_VALIDATION_RULES_JSON_FILE_NAME, 'r') as f:
		return json.load(f)

def get_validation_info_from_excel(validation_rule, xl_file):
	"""Extract validation info from Excel based on validation rule configuration."""
	if not isinstance(validation_rule, dict):
		return []
	
	source_type = validation_rule.get('sourceType')
	tab_name = validation_rule.get('tabName')
	header_value = validation_rule.get('headerValue')
	column_number = validation_rule.get('columnNumber')
	row_number = validation_rule.get('rowNumber')
	
	try:
		if source_type == 'columnWithHeader':
			df = pd.read_excel(xl_file, sheet_name=tab_name)
			if header_value in df.columns:
				return df[header_value].dropna().tolist()
		elif source_type == 'column':
			df = pd.read_excel(xl_file, sheet_name=tab_name)
			if column_number and column_number <= len(df.columns):
				return df.iloc[:, column_number - 1].dropna().tolist()
		elif source_type == 'headerRow':
			df = pd.read_excel(xl_file, sheet_name=tab_name)
			return df.columns.dropna().tolist()
		elif source_type == 'row':
			df = pd.read_excel(xl_file, sheet_name=tab_name)
			if row_number and row_number <= len(df):
				return df.iloc[row_number-1].dropna().tolist()
	except Exception as e:
		print(f"Error loading validation info from {tab_name}: {e}")
	
	return []

def extract_regex_and_examples(matchedKey, permissible_values):
	"""Extract regex pattern and examples from permissible values text."""
	if not isinstance(permissible_values, str):
		return ""
	
	# After removing first instance of matchedKey, regex is on the first line
	regex = permissible_values.replace(matchedKey + "\n", "", 1).splitlines()[0].strip()
	
	# If ends with Or Not available, append to regex
	endsWithNotApplicable = re.search(r"[\s]+Or[\s]+Not available$", permissible_values.strip(), re.IGNORECASE)
	if endsWithNotApplicable:
		# print(endsWithNotApplicable)
		# print(permissible_values)
		regex += "|^Not available$"

	return regex

def process_requirements(requirements, required_if_stripped_text):
	"""Process requirements to determine requiredAlways and requiredIf."""
	if not isinstance(requirements, str):
		return None, None
	
	requirements = requirements.strip()
	
	if requirements == "Required":
		return True, None
	
	if requirements == "Optional":
		return False, None
	
	# Strip the specified text from requirements
	remaining_text = requirements
	for text_to_strip in required_if_stripped_text:
		remaining_text = remaining_text.replace(text_to_strip, "", 1).strip()
	
	if remaining_text and remaining_text != requirements:
		return False, remaining_text
	
	return None, None

def determine_validation_type_and_info(permissible_values, validation_rules_by_text, xl_file):
	"""Determine validation type and info based on permissible values and validation rules."""
	if not isinstance(permissible_values, str):
		return None, None
	
	keys = list(validation_rules_by_text.keys());
	for key in keys:
		# direct match or if value starts with key followed by line break
		if permissible_values == key or permissible_values.startswith(key + '\n'):
			rule = validation_rules_by_text[key]
			return process_validation_rule(key, rule,  permissible_values, xl_file)
	
	# Fallback: if no validation rules found and text has line breaks, treat as list
	if '\n' in permissible_values.strip():
		# Split by line breaks and clean up each line
		lines = [line.strip() for line in permissible_values.strip().splitlines() if line.strip()]
		if lines:
			return "list", lines
	
	return None, None

def process_validation_rule(matchedKey,rule,permissible_values, xl_file):
	"""Process a validation rule to determine type and info."""
	if rule == "regex":
		regex = extract_regex_and_examples(matchedKey, permissible_values)
		return "regex", {"regex": regex, "message":permissible_values}
	elif isinstance(rule, dict):
		options = [s.strip() for s in get_validation_info_from_excel(rule, xl_file)]
		return "list", options
	else:
		return rule, None

def determine_data_type(type_value, permissible_values):
	"""Determine the data type based on Type and Permissible Values columns."""
	if type_value == "Boolean":
		return "Text"
	elif isinstance(permissible_values, str) and permissible_values == "Format YYYY-MM-DD":
		return "JSON"
	else:
		return type_value

def generate_validation_rules():
	"""Generate the validation rules JSON file."""
	# Load settings
	map_generation_settings = load_map_generation_settings()
	required_if_stripped_text = map_generation_settings.get('requiredIfStrippedText', [])
	validation_rules_by_text = map_generation_settings.get('validationRulesByText', {})
	
	# Load Excel file
	xl_file = settings.MOHCCN_STANDARD_DEFINITION_XLSX_FILE_NAME
	df = pd.read_excel(xl_file, sheet_name=0)
	
	# Get the MoHCCN Clinical Field column name
	mohccn_column = None
	for col in df.columns:
		if col.startswith('MoHCCN Clinical Field'):
			mohccn_column = col
			break
	
	if not mohccn_column:
		raise ValueError("Could not find MoHCCN Clinical Field column")
	
	result = {}
	
	# Process each row
	for _, row in df.iterrows():
		schema = row['Schema'].strip()
		field = row[mohccn_column].strip()
		requirements = row['Requirements'].strip()
		type_value = row['Type'].strip()
		description = row['Field Description']
		permissible_values = row['Permissible Values']
		
		
		if pd.isna(schema) or pd.isna(field):
			continue
		
		# Initialize schema if not exists
		if schema not in result:
			result[schema] = {}
		
		# Determine data type
		data_type = determine_data_type(type_value, permissible_values)
		
		# Process requirements
		required_always, required_if = process_requirements(requirements, required_if_stripped_text)
		
		# Determine validation type and info
		validation_type, validation_info = determine_validation_type_and_info(permissible_values, validation_rules_by_text, xl_file)
		
		# Create field object
		field_obj = {
			"dataType": data_type
		}
		
		if required_always == True:
			field_obj["requiredAlways"] = required_always
		
		if required_if:
			field_obj["requiredIf"] = required_if
		
		field_obj["description"] = description
		
		if validation_type:
			field_obj["validationType"] = validation_type
			
		if validation_info:
			field_obj["validationInfo"] = validation_info
		
		result[schema][field] = field_obj
	
	# Save to JSON file
	output_file = settings.GENERATED_VALIDATION_RULES_JSON_FILE_NAME
	with open(output_file, 'w') as f:
		json.dump(result, f, indent='\t')
	
	print(f"Validation rules generated successfully: {output_file}")

if __name__ == "__main__":
	generate_validation_rules() 