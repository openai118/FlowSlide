#!/usr/bin/env python3
"""
Script to fix Tailwind CSS CDN warnings by replacing CDN links with local CSS links
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List

# Add the src directory to the path so we can import our modules
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from flowslide.database.database import AsyncSessionLocal
from flowslide.database.service import DatabaseService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TailwindCDNFixer:
    """Fix Tailwind CSS CDN warnings by replacing CDN links with local CSS links"""

    def __init__(self):
        self.cdn_pattern = re.compile(
            r'<script\s+src\s*=\s*["\']https?://cdn\.tailwindcss\.com["\']\s*>\s*</script>',
            re.IGNORECASE | re.MULTILINE
        )
        self.local_css_link = '<link href="/static/css/tailwind.min.css" rel="stylesheet">'

    def fix_html_template(self, html_content: str) -> str:
        """Replace CDN link with local CSS link in HTML template"""
        if not html_content:
            return html_content

        # Replace CDN script tag with local CSS link
        fixed_content = self.cdn_pattern.sub(self.local_css_link, html_content)

        # Also handle any variations or multiple occurrences
        fixed_content = re.sub(
            r'<script[^>]*src\s*=\s*["\']https?://cdn\.tailwindcss\.com[^>]*>\s*</script>',
            self.local_css_link,
            fixed_content,
            flags=re.IGNORECASE | re.MULTILINE
        )

        return fixed_content

    async def fix_database_templates(self) -> int:
        """Fix all templates in the database"""
        logger.info("Starting to fix templates in database...")

        try:
            async with AsyncSessionLocal() as session:
                db_service = DatabaseService(session)

                # Get all templates
                templates = await db_service.get_all_global_master_templates(active_only=False)
                logger.info(f"Found {len(templates)} templates in database")

                fixed_count = 0

                for template in templates:
                    original_html = template.html_template
                    fixed_html = self.fix_html_template(original_html)

                    # Check if the template was actually changed
                    if fixed_html != original_html:
                        # Update the template
                        update_data = {"html_template": fixed_html}
                        success = await db_service.update_global_master_template(template.id, update_data)

                        if success:
                            logger.info(f"Fixed template: {template.template_name} (ID: {template.id})")
                            fixed_count += 1
                        else:
                            logger.error(f"Failed to update template: {template.template_name} (ID: {template.id})")
                    else:
                        logger.debug(f"No changes needed for template: {template.template_name} (ID: {template.id})")

                logger.info(f"Successfully fixed {fixed_count} templates in database")
                return fixed_count

        except Exception as e:
            logger.error(f"Error fixing database templates: {e}")
            raise

    def fix_template_examples(self) -> int:
        """Fix template examples JSON files"""
        logger.info("Starting to fix template examples...")

        template_examples_dir = Path(__file__).parent / "template_examples"
        if not template_examples_dir.exists():
            logger.warning(f"Template examples directory not found: {template_examples_dir}")
            return 0

        fixed_count = 0

        # Process all JSON files in template_examples directory
        for json_file in template_examples_dir.glob("*.json"):
            try:
                logger.info(f"Processing template file: {json_file.name}")

                # Read the JSON file
                with open(json_file, 'r', encoding='utf-8') as f:
                    template_data = json.load(f)

                # Check if it has html_template
                if "html_template" in template_data:
                    original_html = template_data["html_template"]
                    fixed_html = self.fix_html_template(original_html)

                    if fixed_html != original_html:
                        # Update the template data
                        template_data["html_template"] = fixed_html

                        # Write back to file
                        with open(json_file, 'w', encoding='utf-8') as f:
                            json.dump(template_data, f, ensure_ascii=False, indent=2)

                        logger.info(f"Fixed template example: {json_file.name}")
                        fixed_count += 1
                    else:
                        logger.debug(f"No changes needed for template example: {json_file.name}")

            except Exception as e:
                logger.error(f"Error processing template file {json_file.name}: {e}")

        logger.info(f"Successfully fixed {fixed_count} template examples")
        return fixed_count

    async def run_all_fixes(self) -> Dict[str, int]:
        """Run all fixes and return summary"""
        logger.info("Starting comprehensive Tailwind CDN fix...")

        results = {}

        # Fix database templates
        try:
            results["database_templates"] = await self.fix_database_templates()
        except Exception as e:
            logger.error(f"Failed to fix database templates: {e}")
            results["database_templates"] = 0

        # Fix template examples
        try:
            results["template_examples"] = self.fix_template_examples()
        except Exception as e:
            logger.error(f"Failed to fix template examples: {e}")
            results["template_examples"] = 0

        total_fixed = sum(results.values())
        logger.info(f"Fix complete! Total items fixed: {total_fixed}")
        logger.info(f"Summary: {results}")

        return results

async def main():
    """Main function"""
    fixer = TailwindCDNFixer()
    results = await fixer.run_all_fixes()

    print("\n" + "="*50)
    print("TAILWIND CDN FIX RESULTS")
    print("="*50)
    print(f"Database templates fixed: {results['database_templates']}")
    print(f"Template examples fixed: {results['template_examples']}")
    print(f"Total items fixed: {sum(results.values())}")
    print("="*50)

    if sum(results.values()) > 0:
        print("\n✅ Successfully fixed Tailwind CDN warnings!")
        print("The warning should no longer appear when viewing templates.")
    else:
        print("\nℹ️  No templates needed fixing (they may already be using local CSS).")

if __name__ == "__main__":
    asyncio.run(main())
