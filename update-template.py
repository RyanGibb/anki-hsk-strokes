import sqlite3
import os
import json

def unicase_collation(s1, s2):
    return (s1.lower() > s2.lower()) - (s1.lower() < s2.lower())

collection_path = os.path.expanduser("~/.local/share/Anki2/User 1/collection.anki2")
conn = sqlite3.connect(collection_path)
conn.create_collation("unicase", unicase_collation)
cursor = conn.cursor()

# Get Recognition template
cursor.execute("""
    SELECT ntid, ord, name, config
    FROM templates
    WHERE name = 'Recognition '
""")

result = cursor.fetchone()
if result:
    ntid, ord, name, config_blob = result

    print(f"Template: {name}")
    print(f"ntid: {ntid}, ord: {ord}")

    # Decode protobuf manually for strings
    # Field 1 (0x0a) is typically question template
    # Field 2 (0x12) is typically answer template

    def read_varint(data, pos):
        """Read a varint from data starting at pos"""
        result = 0
        shift = 0
        while True:
            byte = data[pos]
            result |= (byte & 0x7f) << shift
            pos += 1
            if not (byte & 0x80):
                break
            shift += 7
        return result, pos

    pos = 0
    fields = {}
    while pos < len(config_blob):
        # Read field tag
        tag = config_blob[pos]
        pos += 1
        field_num = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 2:  # Length-delimited (strings)
            length, pos = read_varint(config_blob, pos)
            value = config_blob[pos:pos+length].decode('utf-8', errors='replace')
            fields[field_num] = value
            pos += length
        else:
            # Skip unknown field types
            if wire_type == 0:  # Varint
                _, pos = read_varint(config_blob, pos)
            else:
                break

    print("\n=== Question (Front) ===")
    print(fields.get(1, 'N/A'))
    print("\n=== Answer (Back) ===")
    print(fields.get(2, 'N/A'))
else:
    print("Recognition template not found")

conn.close()
