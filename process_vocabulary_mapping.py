import pandas as pd
import requests
import json
from urllib.parse import quote
import time
import traceback
import csv
import os
import settings
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, NamedStyle
from openpyxl.utils.dataframe import dataframe_to_rows


def process_vocabulary_mapping():
	"""Process vocabulary CSV line by line and generate mapped CSV file with concept search results."""
	
	input_csv_file = settings.GENERATED_UNMAPPED_VOCAB_CSV_FILE_NAME # 'mohccn_vocabulary_unmapped.csv'
	input_excel_file = settings.EXISTING_MAPPED_VOCAB_XLSX_FILE_NAME # 'mohccn_vocabulary_mapped.xlsx'
	output_csv_file = f'{settings.GENERATED_MAPPED_VOCAB_FILE_NAME_PREFIX}{time.strftime("%Y%m%d_%H%M")}.csv'
	output_excel_file = f'{settings.GENERATED_MAPPED_VOCAB_FILE_NAME_PREFIX}{time.strftime("%Y%m%d_%H%M")}.xlsx'
	
	# Load existing mappings if Excel file exists
	existing_mappings = {}

	# Track notes for rows with no mappings
	existing_notes = {}

	if os.path.exists(input_excel_file):
		print("Loading existing mappings from Excel file...")
		try:
			existing_df = pd.read_excel(input_excel_file, dtype=str)
			for _, row in existing_df.iterrows():
				# Create key from Schema, Field, and Original Term
				key = (str(row.get('Schema', '')), str(row.get('Field', '')), str(row.get('Original Term', '')))

				# Only consider rows that have a value in Mapped By column
				if pd.notna(row.get('Mapped By', '')) and str(row.get('Mapped By', '')).strip() != '':

					# Store the mapping values
					existing_mappings[key] = {
						 'Preferred Target Classes': str(row.get('Preferred Target Classes', '')),
						 'Preferred Target Domains': str(row.get('Preferred Target Domains', '')),
						 'Preferred Target Vocabularies': str(row.get('Preferred Target Vocabularies', '')),
						 'Mapped Term': str(row.get('Mapped Term', '')),
						 'Concept ID': str(row.get('Concept ID', '')),
						 'Concept Code': str(row.get('Concept Code', '')),
						 'Term Type': str(row.get('Term Type', '')),
						 'Status': str(row.get('Status', '')),
						 'Match Type': str(row.get('Match Type', '')),
						 'Class': str(row.get('Class', '')),
						 'Domain': str(row.get('Domain', '')),
						 'Vocabulary': str(row.get('Vocabulary', '')),
						 'Mapped By': str(row.get('Mapped By', '')),
						 'Approved By': str(row.get('Approved By', '')),
						 'Review URL': str(row.get('Review URL', '')),
						 'Notes': str(row.get('Notes', ''))
					 }
					# Convert any NaN values to empty strings in existing mappings
					for field in existing_mappings[key]:
						if pd.isna(existing_mappings[key][field]) or existing_mappings[key][field] == 'nan':
							existing_mappings[key][field] = ''
				elif not pd.isna(row.get('Notes', '')):
					existing_notes[key] = str(row.get('Notes', ''))

			print(f"Loaded {len(existing_mappings)} existing mappings")
			print(f"Loaded {len(existing_notes)} un-mapped notes")
		except Exception as e:
			print(f"Warning: Could not load existing mappings: {e}")
			existing_mappings = {}
	
	# Define the new columns for the mapped data
	new_columns = [
		'Mapped Term', 'Concept ID', 'Concept Code', 'Term Type', 'Status',
		'Match Type', 'Class', 'Domain', 'Vocabulary', 'Mapped By', 'Approved By', 'Review URL', 'Notes'
	]
	
	# Read the header from input file to get original columns
	print("Reading input file header...")
	with open(input_csv_file, 'r', newline='', encoding='utf-8') as f:
		reader = csv.reader(f)
		header = next(reader)
	
	# Create output file with headers
	print("Creating output file with headers...")
	output_columns = header + new_columns
	
	with open(output_csv_file, 'w', newline='', encoding='utf-8') as f:
		writer = csv.writer(f)
		writer.writerow(output_columns)
	
	# Process file line by line
	print("Processing vocabulary CSV line by line...")
	row_count = 0
	processed_count = 0
	
	with open(input_csv_file, 'r', newline='', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		
		for row in reader:
			row_count += 1
			
			# Process only the first 10 rows for testing
			# if row_count > 10:
				# break
				
			if row_count % 10 == 0:  # Progress indicator every 10 rows
				print(f"{row_count} ", end="", flush=True)
			
			# Get values from the current row
			original_term = row['Original Term']
			schema = row.get('Schema', '')
			field = row.get('Field', '')
			preferred_classes = row.get('Preferred Target Classes', '')
			preferred_domains = row.get('Preferred Target Domains', '' )
			preferred_vocabs = row.get('Preferred Target Vocabularies', '')
			
			base_url = settings.VOCAB_SERVER_SEARCH_BY_TERM_URL # "http://localhost/dhdp-vocab-search/index.php"
			params = {
				'term': original_term,
				'limit': 10,
				'preferredVocabs': preferred_vocabs if preferred_vocabs else '',
				'preferredDomains': preferred_domains if preferred_domains else '',
				'preferredClasses': preferred_classes if preferred_classes else ''
			}
			

			# Initialize new column values
			mapped_values = [''] * len(new_columns)

			# Check if we have an existing mapping for this combination
			key = (str(schema), str(field), str(original_term))
			if key in existing_mappings:
				# print(f"Loaded {schema}.{field} - {original_term}")
				print(".", end="", flush=True)
				existing_mapping = existing_mappings[key]
				mapped_values = [
					existing_mapping['Mapped Term'],
					existing_mapping['Concept ID'],
					existing_mapping['Concept Code'],
					existing_mapping['Term Type'],
					existing_mapping['Status'],
					existing_mapping['Match Type'],
					existing_mapping['Class'],
					existing_mapping['Domain'],
					existing_mapping['Vocabulary'],
					existing_mapping['Mapped By'],
					existing_mapping['Approved By'],
					existing_mapping['Review URL'],
					existing_mapping['Notes']
				]

				# Use preserved preferred target values from existing mapping
				preferred_classes = existing_mapping['Preferred Target Classes']
				preferred_domains = existing_mapping['Preferred Target Domains']
				preferred_vocabs = existing_mapping['Preferred Target Vocabularies']

				# Set Review URL, preserving "Preferred" properties
				params['preferredClasses'] = preferred_classes
				params['preferredDomains'] = preferred_domains
				params['preferredVocabs'] = preferred_vocabs
				query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])

				mapped_values[11] = f"{base_url}?{query_string}&mode=html&selectedId={existing_mapping['Concept ID']}&selectedName={quote(existing_mapping['Mapped Term'])}"

				# if pd.isna(mapped_values[10]):
				#	 mapped_values[10] = ''
				# if pd.isna(mapped_values[12]):
				#	 mapped_values[12] = ''
				# print(mapped_values)
			else:
				# Build the API URL
				# URL encode the parameters
				query_string = '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
				url = f"{base_url}?{query_string}"
				# print(url)
			
				
				try:
					# Make the API request
					response = requests.get(url, timeout=30)
					response.raise_for_status()
					
					# Parse JSON response
					data = response.json()
					if data and len(data) > 0:
						# Count exact matches
						exact_match_count = sum(1 for result in data.values() if result.get('matchType') == 'Exact')
						inexact_match_count = sum(1 for result in data.values() if result.get('matchType') == 'Inexact')

						first_key = next(iter(data))

						# Get the first JSON object
						first_result = data[first_key]
						
						# Extract values from the first result
						mapped_values[0] = first_result.get('conceptName', '')  # Mapped Term
						mapped_values[1] = first_result.get('conceptId', '')	# Concept ID
						mapped_values[2] = first_result.get('conceptCode', '')  # Concept Code
						mapped_values[3] = first_result.get('termType', '')	 # Term Type
						mapped_values[4] = first_result.get('conceptStatus', '')  # Status
						mapped_values[5] = first_result.get('matchType', '')	# Match Type
						mapped_values[6] = first_result.get('classId', '')	  # Class
						mapped_values[7] = first_result.get('domainId', '')	 # Domain
						mapped_values[8] = first_result.get('vocabId', '')	  # Vocabulary

						if exact_match_count == 1:
							mapped_values[9] = '[Your Name]'
						elif exact_match_count > 1 and mapped_values[5] == 'Exact':
							mapped_values[5] += "*" * exact_match_count
						elif inexact_match_count > 1 and mapped_values[5] == 'Inexact':
							mapped_values[5] += "*"
						
					else:
						mapped_values[0] = mapped_values[1] = mapped_values[2] = mapped_values[3] = mapped_values[4] = mapped_values[5] = mapped_values[6] = mapped_values[7] = mapped_values[8] = ''
						mapped_values[5] = 'No Match'
					
					# mapped_values[9] and mapped_values[10] are 'Mapped By' and 'Approved By' - left empty for manual entry
					mapped_values[11] = url + "&mode=html"		 # Review URL

					if key in existing_notes:
						mapped_values[12] = existing_notes[key]

					# Add a small delay to avoid overwhelming the server
					time.sleep(0.1)
					
				# except requests.exceptions.RequestException as e:
				#	 print(f"Error processing row {row_count}: {e}")
				#	 continue
				except json.JSONDecodeError as e:
					print(f"Error parsing JSON for row {row_count}: {e}")
					continue
				except Exception as e:
					traceback.print_exc()
					# print(f"Unexpected error processing row {row_count}: {e}")
					continue
			
			# Write the processed row to output file
			output_row = list(row.values()) + mapped_values
			# Update preferred target values with preserved values from existing mapping
			output_row[3] = preferred_classes
			output_row[4] = preferred_domains
			output_row[5] = preferred_vocabs
			with open(output_csv_file, 'a', newline='', encoding='utf-8') as f:
				writer = csv.writer(f)
				writer.writerow(output_row)
			
			processed_count += 1
	
	print(f"\nVocabulary mapping completed successfully!")
	print(f"Output file: {output_csv_file}")
	print(f"Total rows processed: {processed_count}")
	
	# Create Excel file with formatting
	print("Creating Excel file with formatting...")
	create_excel_with_formatting(output_csv_file, output_excel_file, output_columns)
	print(f"Excel file created: {output_excel_file}")


def create_excel_with_formatting(csv_file, excel_file, columns):
	"""Create Excel file with row highlighting and hyperlinks."""
	
	# Read the CSV file
	df = pd.read_csv(csv_file)
	
	# Create a new workbook and select the active sheet
	wb = Workbook()
	ws = wb.active
	ws.title = "Vocabulary Mapping"
	
	# Create a text style for all cells
	text_style = NamedStyle(name="text_style")
	text_style.number_format = '@'  # Text format
	
	# Write headers
	for col_idx, col_name in enumerate(columns, 1):
		cell = ws.cell(row=1, column=col_idx, value=col_name)
		cell.style = text_style
	
	# Find the column indices (0-based)
	match_type_col_idx = None
	search_url_col_idx = None
	mapped_term_col_idx = None
	for idx, col_name in enumerate(columns):
		if col_name == 'Match Type':
			match_type_col_idx = idx + 1  # Convert to 1-based
		elif col_name == 'Review URL':
			search_url_col_idx = idx + 1  # Convert to 1-based
		elif col_name == 'Mapped Term':
			mapped_term_col_idx = idx + 1  # Convert to 1-based
	
	# Verify column indices were found
	if mapped_term_col_idx is None:
		print("ERROR: Could not find 'Mapped Term' column!")
		print(f"Available columns: {columns}")
		return
	if match_type_col_idx is None:
		print("ERROR: Could not find 'Match Type' column!")
		print(f"Available columns: {columns}")
		return
	
	# Define highlight fills
	row_highlight_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")  # Yellow for entire row
	cell_highlight_fill = PatternFill(start_color="FFE6CC", end_color="FFE6CC", fill_type="solid")  # Light orange for single cell
	
	# Define hyperlink font style (blue with underline)
	hyperlink_font = Font(color="0000FF", underline="single")
	
	# Process all rows in a single pass
	print("Processing all rows and applying formatting...")
	for row_idx, row_data in enumerate(df.values, 2):  # Start from row 2 (after header)
		# Write data to cells
		for col_idx, value in enumerate(row_data, 1):
			cell = ws.cell(row=row_idx, column=col_idx, value=value)
			cell.style = text_style  # Apply text formatting to all cells
		
		# Get values for formatting decisions
		mapped_term_value = row_data[mapped_term_col_idx - 1] if mapped_term_col_idx <= len(row_data) else None
		match_type_value = row_data[match_type_col_idx - 1] if match_type_col_idx <= len(row_data) else None
		
		# Check if mapped_term_value is float and nan
		if isinstance(mapped_term_value, float) and pd.isna(mapped_term_value):
			mapped_term_value = ''
		
		# Apply highlighting based on Mapped Term value
		if not mapped_term_value or str(mapped_term_value).strip() == '':
			ws.cell(row=row_idx, column=match_type_col_idx).fill = row_highlight_fill
		
		# Apply highlighting based on Match Type value
		elif match_type_value and '*' in str(match_type_value):
			ws.cell(row=row_idx, column=match_type_col_idx).fill = cell_highlight_fill
		
		# Convert Review URL to hyperlink
		if search_url_col_idx and search_url_col_idx <= len(row_data):
			url_value = row_data[search_url_col_idx - 1]
			if url_value:
				cell = ws.cell(row=row_idx, column=search_url_col_idx)
				cell.value = "Review"
				cell.hyperlink = url_value
				cell.font = hyperlink_font
				# cell.style = text_style  # Maintain text formatting for hyperlink cells
	
	# Save the workbook
	wb.save(excel_file)


if __name__ == "__main__":
	process_vocabulary_mapping() 