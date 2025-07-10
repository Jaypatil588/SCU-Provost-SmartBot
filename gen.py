import os
import json
import glob

# --- CONFIGURATION ---
# The directory where your scraped JSON files are stored.
DATA_DIR = "scraped"
OUTPUT_FILENAME = "gen.json"

def create_file_url_map(directory):
    """
    Scans a directory for .json files, extracts the 'sourceURL' from each,
    and returns a dictionary mapping the filename to its source URL.
    """
    print(f"Scanning '{directory}' for JSON files...")
    file_url_map = {}
    
    # Check if the directory exists
    if not os.path.isdir(directory):
        print(f"Error: Directory '{directory}' not found.")
        return None

    json_files = glob.glob(os.path.join(directory, '*.json'))
    
    if not json_files:
        print(f"Warning: No .json files found in '{directory}'.")
        return {}

    # Process each file
    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Safely get the sourceURL from the nested metadata
                source_url = data.get('metadata', {}).get('sourceURL')
                if source_url:
                    # Use the base filename as the key
                    file_url_map[os.path.basename(file_path)] = source_url
                else:
                    print(f"  - Skipping {os.path.basename(file_path)} (no sourceURL found)")
        except json.JSONDecodeError:
            print(f"  - Skipping {os.path.basename(file_path)} (invalid JSON)")
        except Exception as e:
            print(f"  - An error occurred with file {os.path.basename(file_path)}: {e}")
            
    print(f"Successfully processed {len(file_url_map)} files.")
    return file_url_map

if __name__ == '__main__':
    # Generate the map
    generated_map = create_file_url_map(DATA_DIR)

    if generated_map is not None:
        # Save the generated dictionary to a JSON file
        try:
            with open(OUTPUT_FILENAME, 'w', encoding='utf-8') as f:
                json.dump(generated_map, f, indent=4)
            print(f"\n--- Success! ---")
            print(f"The File-to-URL map has been saved to '{OUTPUT_FILENAME}'.")
        except Exception as e:
            print(f"\n--- Error ---")
            print(f"Failed to save the file. Error: {e}")
