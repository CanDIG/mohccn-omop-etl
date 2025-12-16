import json
import csv
import os
import settings

def generate_vocabulary():
	"""Generate vocabulary CSV file from validation rules JSON."""
	
	# Load validation rules
	with open(settings.GENERATED_VALIDATION_RULES_JSON_FILE_NAME, 'r') as f:
		validation_rules = json.load(f)
	
	# Define CSV headers
	headers = ['Schema', 'Field', 'Original Term', 'Preferred Target Classes', 'Preferred Target Domains', 'Preferred Target Vocabularies']
	
	# Dictionary to store existing mappings
	existing_mappings = {}
	
	# Check if CSV file already exists and load existing mappings
	output_file_name = settings.GENERATED_UNMAPPED_VOCAB_CSV_FILE_NAME
	if os.path.exists(output_file_name):
		with open(output_file_name, 'r', newline='', encoding='utf-8') as csvfile:
			reader = csv.DictReader(csvfile)
			for row in reader:
				# Only load mapping if at least one Preferred Target column has a value
				preferred_classes = row['Preferred Target Classes']
				preferred_domains = row['Preferred Target Domains']
				preferred_vocabularies = row['Preferred Target Vocabularies']
				
				if preferred_classes or preferred_domains or preferred_vocabularies:
					# Create a key from Schema, Field, and Original Term
					key = (row['Schema'], row['Field'], row['Original Term'])
					existing_mappings[key] = {
						'Preferred Target Classes': preferred_classes,
						'Preferred Target Domains': preferred_domains,
						'Preferred Target Vocabularies': preferred_vocabularies
					}
		print(f"Loaded {len(existing_mappings)} existing mappings with values from mohccn_vocabulary_unmapped.csv")
	
	# Open CSV file for writing
	with open(output_file_name, 'w', newline='', encoding='utf-8') as csvfile:
		writer = csv.writer(csvfile)
		
		# Write headers
		writer.writerow(headers)
		
		row_count = 0
		
		# Process each schema
		for schema_name, schema_data in validation_rules.items():
			# Process each field in the schema
			for field_name, field_data in schema_data.items():
				# Check if validation type is "list"
				if field_data.get('validationType') == 'list':
					validation_info = field_data.get('validationInfo', [])
					
					# Process each option in validationInfo array
					for option in validation_info:
						if option:  # Skip empty options
							# Create key to check for existing mapping
							key = (schema_name, field_name, option)
							
							# Get existing values or use empty strings
							if key in existing_mappings:
								existing_values = existing_mappings[key]
								preferred_classes = existing_values['Preferred Target Classes']
								preferred_domains = existing_values['Preferred Target Domains']
								preferred_vocabularies = existing_values['Preferred Target Vocabularies']
							else:
								preferred_classes = ''
								preferred_domains = ''
								preferred_vocabularies = ''
							
							# Write row directly to CSV
							writer.writerow([
								schema_name,
								field_name,
								option,
								preferred_classes,
								preferred_domains,
								preferred_vocabularies
							])
							row_count += 1
	
	print(f"Vocabulary CSV file generated successfully: {output_file_name}")
	print(f"Total rows: {row_count}")

if __name__ == "__main__":
	generate_vocabulary() 