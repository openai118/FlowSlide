import sqlite3
import os

def check_templates():
    # Try different database paths
    db_paths = [
        'data/flowslide.db',
        'src/data/flowslide.db',
        'flowslide.db'
    ]

    for db_path in db_paths:
        if os.path.exists(db_path):
            print(f"Found database at: {db_path}")
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='global_master_templates'")
                if cursor.fetchone():
                    print("global_master_templates table exists")

                    # Get template count
                    cursor.execute("SELECT COUNT(*) FROM global_master_templates")
                    count = cursor.fetchone()[0]
                    print(f"Template count: {count}")

                    if count > 0:
                        # Get first template with full content
                        cursor.execute("SELECT id, template_name, html_template FROM global_master_templates LIMIT 1")
                        template = cursor.fetchone()
                        print(f'ID: {template[0]}, Name: {template[1]}')
                        print(f'HTML Length: {len(template[2])}')

                        # Check for style tags
                        html_content = template[2]
                        if '<style>' in html_content:
                            print("✓ Contains <style> tags")
                            # Extract style content
                            import re
                            style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL)
                            if style_matches:
                                print(f"Style content length: {len(style_matches[0])}")
                                print(f"Style preview: {style_matches[0][:300]}...")
                        else:
                            print("✗ No <style> tags found")

                        if 'class=' in html_content:
                            print("✓ Contains CSS classes")
                        else:
                            print("✗ No CSS classes found")

                        print(f'HTML Preview: {html_content[:500]}...')
                        print('---')
                    else:
                        print("No templates found in database")
                else:
                    print("global_master_templates table does not exist")

                conn.close()
                return
            except Exception as e:
                print(f"Error accessing database {db_path}: {e}")
                continue

    print("No database found")

if __name__ == "__main__":
    check_templates()
