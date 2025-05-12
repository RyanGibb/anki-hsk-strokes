import sqlite3
import os

def unicase_collation(s1, s2):
    return (s1.lower() > s2.lower()) - (s1.lower() < s2.lower())

def update_anki_db():
    collection_path = os.path.expanduser("~/.local/share/Anki2/User 1/collection.anki2")
    
    conn = sqlite3.connect(collection_path)
    conn.create_collation("unicase", unicase_collation)
    cursor = conn.cursor()

    # 1. Add Stroke order field to all note types with Simplified field
    cursor.execute("""
        SELECT DISTINCT ntid FROM fields
        WHERE name = 'Simplified'
    """)
    note_type_ids = [row[0] for row in cursor.fetchall()]

    for ntid in note_type_ids:
        # Check if Stroke order exists
        cursor.execute("""
            SELECT 1 FROM fields
            WHERE ntid = ? AND name = 'StrokeOrder'
        """, (ntid,))
        if not cursor.fetchone():
            # Get max ord and config from existing field
            cursor.execute("""
                SELECT MAX(ord), config FROM fields
                WHERE ntid = ?
            """, (ntid,))
            max_ord, sample_config = cursor.fetchone()
            
            # Add new field
            cursor.execute("""
                INSERT INTO fields (ntid, ord, name, config)
                VALUES (?, ?, ?, ?)
            """, (ntid, max_ord + 1, "StrokeOrder", sample_config))

    # 2. Update all notes to match field count
    cursor.execute("""
        SELECT n.id, n.mid, n.flds, 
               (SELECT COUNT(*) FROM fields WHERE ntid = n.mid) as required_fields
        FROM notes n
    """)
    
    for note_id, model_id, flds, required_count in cursor.fetchall():
        fields = flds.split("\x1f")
        
        # Pad with empty fields if needed
        if len(fields) < required_count:
            fields += [""] * (required_count - len(fields))
        
        # Truncate if somehow longer (shouldn't happen)
        fields = fields[:required_count]

        # 3. Update Stroke order content
        cursor.execute("""
            SELECT f.ord 
            FROM fields f
            WHERE f.ntid = ? 
            AND f.name IN ('Simplified', 'StrokeOrder')
        """, (model_id,))
        ords = cursor.fetchall()
        
        simplified_ord = None
        stroke_ord = None
        for (ord,) in ords:
            cursor.execute("""
                SELECT name FROM fields
                WHERE ntid = ? AND ord = ?
            """, (model_id, ord))
            name = cursor.fetchone()[0]
            if name == "Simplified":
                simplified_ord = ord
            elif name == "StrokeOrder":
                stroke_ord = ord

        if simplified_ord is not None and stroke_ord is not None:
            simplified = fields[simplified_ord]
            fields[stroke_ord] = "".join(
                f'<img width="640" src="{char}.svg">' 
                for char in simplified.strip()
            )

        # Update the note
        cursor.execute("""
            UPDATE notes
            SET flds = ?
            WHERE id = ?
        """, ("\x1f".join(fields), note_id))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_anki_db()
