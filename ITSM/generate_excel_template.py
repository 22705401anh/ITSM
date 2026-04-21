import os
import pandas as pd
from openpyxl import Workbook

# Generate the template Excel file template
template_data = {
    "user_name": ["John Doe", "Jane Smith", ""],
    "pc_name": ["JD-DESKTOP-01", "", ""],
    "pc_serial_number": ["PC-123456", "PC-654321", ""],
    "pc_model": ["Dell Latitude 5440", "Lenovo ThinkPad", ""],
    "assigned_status": ["Assigned", "Assigned", "Available"],
    "monitor_model": ["Dell U2720Q", "HP 24f", ""],
    "monitor_serial_number": ["MON-98765", "MON-56789", ""],
    "docking_station_model": ["Dell WD19", "", "ThinkPad Dock"],
    "docking_station_serial_number": ["DOCK-111", "", "DOCK-222"],
    "phone_model": ["iPhone 13 Pro", "Samsung S23", ""],
    "phone_serial_number": ["PH-123", "PH-456", ""],
    "phone_number": ["555-0199", "555-2022", ""],
    "notes": ["New hire set up on Oct 1st", "Monitor replacement", "Spare dock"]
}

df = pd.DataFrame(template_data)

# Specify the output directory inside the app
output_dir = os.path.join(os.path.dirname(__file__), 'app', 'web', 'static', 'downloads')
os.makedirs(output_dir, exist_ok=True)
template_path = os.path.join(output_dir, 'hardware_import_template.xlsx')

df.to_excel(template_path, index=False)
print(f"Sample Excel template generated at: {template_path}")
