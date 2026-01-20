import sqlite3
import os
import time

def unicase_collation(s1, s2):
    return (s1.lower() > s2.lower()) - (s1.lower() < s2.lower())

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

def write_varint(value):
    """Encode an integer as a varint"""
    result = bytearray()
    while value > 0x7f:
        result.append((value & 0x7f) | 0x80)
        value >>= 7
    result.append(value & 0x7f)
    return bytes(result)

def decode_template_config(config_blob):
    """Decode protobuf config blob"""
    pos = 0
    fields = {}
    while pos < len(config_blob):
        tag = config_blob[pos]
        pos += 1
        field_num = tag >> 3
        wire_type = tag & 0x7

        if wire_type == 2:  # Length-delimited (strings)
            length, pos = read_varint(config_blob, pos)
            value = config_blob[pos:pos+length].decode('utf-8')
            fields[field_num] = value
            pos += length
        elif wire_type == 0:  # Varint
            _, pos = read_varint(config_blob, pos)
        else:
            break
    return fields

def encode_template_config(fields):
    """Encode fields back to protobuf config blob"""
    result = bytearray()
    for field_num in sorted(fields.keys()):
        value = fields[field_num]
        if isinstance(value, str):
            encoded = value.encode('utf-8')
            # Write field tag
            result.append((field_num << 3) | 2)
            # Write length
            result.extend(write_varint(len(encoded)))
            # Write value
            result.extend(encoded)
    return bytes(result)

# JavaScript to add Pleco links to sentence (for both front and back)
def make_pleco_script(exclude_target=False):
    exclude_check = """
  const targetWord = '{{Simplified}}'.trim();
""" if exclude_target else "  const targetWord = null;\n"

    return f"""
<script>
(function() {{
  const sentenceElem = document.querySelector('.sentence');
  if (!sentenceElem) return;

  const simplified = sentenceElem.textContent.trim();
  const pinyinRaw = '{{{{SentencePinyin.2}}}}'.trim();
{exclude_check}
  if (!simplified || !pinyinRaw) return;

  // Strip HTML tags from pinyin
  const tempDiv = document.createElement('div');
  tempDiv.innerHTML = pinyinRaw;
  const pinyin = tempDiv.textContent.trim();

  // Split pinyin by spaces to get word boundaries
  const pinyinWords = pinyin.split(/\\s+/);

  // Count syllables in each pinyin word to determine character count
  function countSyllables(pinyinWord) {{
    // Remove punctuation and numbers
    const clean = pinyinWord.replace(/[0-9.,!?;:，。！？；：""'']/g, '');
    if (!clean) return 0;

    // Count consonant groups (each syllable starts with consonants or a vowel)
    const consonantGroups = clean.match(/[bcdfghjklmnpqrstwxyz]+/gi);
    const startsWithVowel = /^[aeiouv]/i.test(clean);

    return (consonantGroups ? consonantGroups.length : 0) + (startsWithVowel ? 1 : 0);
  }}

  const charCounts = pinyinWords.map(countSyllables);

  // Segment the Chinese text based on character counts
  let charIndex = 0;
  const linkedWords = [];

  for (let i = 0; i < charCounts.length; i++) {{
    const count = charCounts[i];

    if (count === 0) {{
      // This was probably punctuation in pinyin, skip ahead in Chinese until we find punctuation
      while (charIndex < simplified.length && /[\\u4e00-\\u9fff]/.test(simplified[charIndex])) {{
        charIndex++;
      }}
      if (charIndex < simplified.length) {{
        linkedWords.push(simplified[charIndex]);
        charIndex++;
      }}
      continue;
    }}

    const word = simplified.slice(charIndex, charIndex + count);

    if (word && /[\\u4e00-\\u9fff]/.test(word)) {{
      // Only link if it contains Chinese characters and is not the target word
      if (targetWord && word === targetWord) {{
        linkedWords.push(word);
      }} else {{
        linkedWords.push('<a href="plecoapi://x-callback-url/s?q=' + encodeURIComponent(word) + '">' + word + '</a>');
      }}
    }} else {{
      linkedWords.push(word);
    }}
    charIndex += count;

    // After each word, check if there's punctuation immediately following
    while (charIndex < simplified.length && !/[\\u4e00-\\u9fff]/.test(simplified[charIndex])) {{
      linkedWords.push(simplified[charIndex]);
      charIndex++;
    }}
  }}

  // Add any remaining characters
  if (charIndex < simplified.length) {{
    linkedWords.push(simplified.slice(charIndex));
  }}

  sentenceElem.innerHTML = linkedWords.join('');
}})();
</script>
"""

pleco_link_script_back = make_pleco_script(exclude_target=False)
pleco_link_script_front = make_pleco_script(exclude_target=True)

# Update the database
collection_path = os.path.expanduser("~/.local/share/Anki2/User 1/collection.anki2")
conn = sqlite3.connect(collection_path)
conn.create_collation("unicase", unicase_collation)
cursor = conn.cursor()

# Get both Recognition and Writing templates
cursor.execute("""
    SELECT ntid, ord, name, config, mtime_secs, usn
    FROM templates
    WHERE name IN ('Recognition ', 'Writing')
""")

results = cursor.fetchall()

for result in results:
    ntid, ord, name, config_blob, mtime_secs, usn = result

    print(f"\nProcessing template: {name}")

    # Decode config
    fields = decode_template_config(config_blob)

    # Get both question and answer templates
    question_html = fields.get(1, '')
    answer_html = fields.get(2, '')

    # Check if script already exists and remove it from both
    script_start_marker = '<script>\n(function() {\n  const sentenceElem = document.querySelector(\'.sentence\');'

    for field_name, html_content in [('question', question_html), ('answer', answer_html)]:
        if script_start_marker in html_content:
            # Find and remove the old script
            start_pos = html_content.find(script_start_marker)
            end_pos = html_content.find('</script>', start_pos)
            if end_pos != -1:
                end_pos += len('</script>')
                # Remove old script (including trailing newline if present)
                if end_pos < len(html_content) and html_content[end_pos] == '\n':
                    end_pos += 1
                html_content = html_content[:start_pos] + html_content[end_pos:]
                print(f"  Removed old Pleco sentence linking script from {field_name}")

        # Update the variable
        if field_name == 'question':
            question_html = html_content
        else:
            answer_html = html_content

    # Add the new scripts based on template type
    if name == 'Recognition ':
        # Add to question (front) - excludes target word
        insert_pos = question_html.find('<hr>')
        if insert_pos != -1:
            question_html = question_html[:insert_pos] + pleco_link_script_front + '\n' + question_html[insert_pos:]
        else:
            question_html += '\n' + pleco_link_script_front
        print(f"  Added script to front (excludes target word)")

    # Add to answer (back) - includes all words (for both Recognition and Writing)
    insert_pos = answer_html.find('<script>\nsetTimeout(function ()')
    if insert_pos == -1:
        # If that script doesn't exist, just append
        answer_html += '\n' + pleco_link_script_back
    else:
        answer_html = answer_html[:insert_pos] + pleco_link_script_back + '\n' + answer_html[insert_pos:]
    print(f"  Added script to back (includes all words)")

    # Update the fields
    fields[1] = question_html
    fields[2] = answer_html

    # Encode back to protobuf
    new_config = encode_template_config(fields)

    # Update the database
    cursor.execute("""
        UPDATE templates
        SET config = ?, mtime_secs = ?, usn = ?
        WHERE ntid = ? AND ord = ?
    """, (new_config, int(time.time()), usn + 1, ntid, ord))

    conn.commit()
    print(f"  Successfully updated {name}template!")

if not results:
    print("No templates found")

conn.close()
