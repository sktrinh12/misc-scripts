import argparse
import os
from rdkit import Chem

def convert_cdxml_to_mol(input_path):
    if not os.path.exists(input_path):
        print(f"Error: File '{input_path}' not found.")
        return

    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
        xml_data = f.read()

    try:
        mols = Chem.MolsFromCDXML(xml_data)
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Filter out any None values (empty fragments in the CDXML)
    valid_mols = [m for m in mols if m is not None]

    if not valid_mols:
        print(f"Error: No valid structures found in {input_path}")
        return

    base_name = os.path.splitext(input_path)[0]
    
    # Handle single vs multiple molecules
    if len(valid_mols) == 1:
        output_file = f"{base_name}.mol"
        Chem.MolToMolFile(valid_mols[0], output_file)
        print(f"Successfully converted to: {output_file}")
    else:
        output_file = f"{base_name}.sdf"
        writer = Chem.SDWriter(output_file)
        for m in valid_mols:
            writer.write(m)
        writer.close()
        print(f"Detected {len(valid_mols)} structures. Saved to: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert CDXML files to MOL/SDF format using RDKit.")
    parser.add_argument("filepath", help="Path to the .cdxml file")

    args = parser.parse_args()
    convert_cdxml_to_mol(args.filepath)
