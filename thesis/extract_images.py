from docx import Document
import io
from PIL import Image
import os

# Create screenshots directory if it doesn't exist
os.makedirs('screenshots', exist_ok=True)

doc = Document('AutoApply_Thesis_v23.docx')

# Map image indices to professional filenames
# Images 1-23 are existing figures, 24-29 are the new follow/unfollow images
fig_mapping = {
    24: 'fig12_follow_feed.png',
    25: 'fig13_follow_company_main_vs_sidebar.png',
    26: 'fig14_followed_companies_table.png',
    27: 'fig15_unfollow_main_button.png',
    28: 'fig16_unfollow_sidebar_counterexample.png',
    29: 'fig17_unfollow_dashboard_result.png',
}

print("Extracting images from DOCX...")
image_count = 0
extracted_new = []

for rel_id, rel in doc.part.rels.items():
    if 'image' in rel.target_ref:
        image_count += 1
        try:
            image_data = rel.target_part.blob
            image = Image.open(io.BytesIO(image_data))
            
            # For the new follow/unfollow images, save with professional names and enhance
            if image_count in fig_mapping:
                filename = fig_mapping[image_count]
                filepath = f'screenshots/{filename}'
                
                # Professional enhancement: ensure good resolution and clarity
                # Resize if needed to maintain consistency (max width 1600px)
                if image.width > 1600:
                    ratio = 1600 / image.width
                    new_size = (1600, int(image.height * ratio))
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                
                # Save as high-quality PNG
                image.save(filepath, 'PNG', quality=95)
                extracted_new.append(filename)
                print(f"  ✓ Extracted: {filename} ({image.size})")
            else:
                # Keep track of existing images
                existing_path = f'screenshots/fig{image_count:02d}.png'
                if not os.path.exists(existing_path):
                    image.save(existing_path, 'PNG')
                    
        except Exception as e:
            print(f"  ✗ Error extracting image {image_count}: {e}")

print(f"\n✓ Successfully extracted {len(extracted_new)} new follow/unfollow images:")
for img in extracted_new:
    print(f"  - {img}")

# Verify files exist
print("\nVerifying extracted files...")
for filename in extracted_new:
    filepath = f'screenshots/{filename}'
    if os.path.exists(filepath):
        size = os.path.getsize(filepath)
        img = Image.open(filepath)
        print(f"  ✓ {filename}: {img.size} ({size} bytes)")
    else:
        print(f"  ✗ {filename}: NOT FOUND")
