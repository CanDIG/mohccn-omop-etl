import pandas as pd
import json
import sys
import os
import settings

def generate_etl_rules():
	"""
	Load MOHCCN to OMOP CDM mapping spreadsheet and generate ETL rules JSON structure
	"""
	
	# Initialize empty rules dictionary
	rules = {}
	
	# Read Excel file 
	df = pd.read_excel(settings.MOHCCN_TO_OMOP_ETL_MODEL_XLSX_FILE_NAME, dtype=str, keep_default_na=False)
	
	# Replace nan with empty string
	# df.fillna('', inplace=True)
	
	current_json_level = None
	current_data_group = None
	current_omop_table = None
	
	# Iterate through rows
	for _, row in df.iterrows():
		json_level = str(row.get('Source JSON Level', '')).strip()
		data_group = str(row.get('DHDP Data Group', '')).strip()
		instruction = str(row.get('Instruction', '')).strip()
		omop_table = str(row.get('OMOP Table', '')).strip()
		
		
		# If new JSON level encountered
		if json_level != '' and json_level != current_json_level:
			current_json_level = json_level
			
		# If new data group encountered
		if data_group != '' and data_group != current_data_group:
			current_data_group = data_group
			
		# If new OMOP table encountered
		if omop_table != '' and omop_table != current_omop_table:
			current_omop_table = omop_table
			
		if instruction != '':
			# print(json_level, data_group, instruction)

			# Create new JSON level object if doesn't exist
			if current_json_level not in rules:
				rules[current_json_level] = {}
				
			
			# Create new data group object if doesn't exist
			if current_data_group and current_data_group not in rules[current_json_level]:
				rules[current_json_level][current_data_group] = {}
			
			# Create new OMOP table object if doesn't exist
			if current_omop_table and current_omop_table not in rules[current_json_level][current_data_group]:
				rules[current_json_level][current_data_group][current_omop_table] = []
			
			# Add instruction details as JSON object
			instruction_obj = {}
			for col in df.columns:
				# Skip Source JSON Level and DHDP Data Group columns
				if col not in ['Source JSON Level', 'DHDP Data Group', 'OMOP Table']:
					value = str(row.get(col, '')).strip()
					if value and value != '':
						instruction_obj[col] = value

			# Only add if we have instruction details
			if instruction_obj:
				rules[current_json_level][current_data_group][current_omop_table].append(instruction_obj)
				
	# Save to JSON file
	output_file = settings.GENERATED_MOHCCN_TO_OMOP_ETL_SETTINGS_JSON_FILE_NAME
	with open(output_file, 'w') as f:
		json.dump(rules, f, indent='\t')
	
	print(f"ETL rules generated successfully: {output_file}")
	

if __name__ == "__main__":
	rules = generate_etl_rules()
