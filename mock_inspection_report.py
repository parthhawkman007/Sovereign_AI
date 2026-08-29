from PIL import Image, ImageDraw, ImageFont

def create_mock_report(filename="inspection_report.jpg"):
    # Create a white A4-ish page
    img = Image.new('RGB', (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # Try to get a basic font
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_text = ImageFont.truetype("arial.ttf", 20)
        font_bold = ImageFont.truetype("arialbd.ttf", 20)
    except:
        font_title = font_text = font_bold = ImageFont.load_default()

    # Draw Header
    draw.text((50, 50), "REFINERY SECTOR 4 - INSPECTION REPORT", fill=(0, 0, 0), font=font_title)
    draw.line([(50, 90), (750, 90)], fill=(0, 0, 0), width=3)
    
    # Draw Meta Data
    draw.text((50, 110), "Date: 2026-08-22", fill=(0, 0, 0), font=font_text)
    draw.text((400, 110), "Inspector: John Doe", fill=(0, 0, 0), font=font_text)
    draw.text((50, 140), "Equipment ID: V-405-B", fill=(0, 0, 0), font=font_text)
    draw.text((400, 140), "Status: REQUIRES MAINTENANCE", fill=(255, 0, 0), font=font_bold)
    
    # Draw Findings Box
    draw.rectangle([50, 200, 750, 300], outline=(0, 0, 0), width=2)
    draw.text((60, 210), "Key Findings:", fill=(0, 0, 0), font=font_bold)
    draw.text((60, 240), "- Micro-fractures detected on flange weld joint W-02.", fill=(0, 0, 0), font=font_text)
    draw.text((60, 260), "- Ultrasonic thickness measurement indicates 2mm wall thinning.", fill=(0, 0, 0), font=font_text)
    
    # Draw Table
    draw.text((50, 350), "Thickness Readings:", fill=(0, 0, 0), font=font_bold)
    # Table header
    draw.rectangle([50, 380, 750, 420], fill=(220, 220, 220), outline=(0, 0, 0))
    draw.text((60, 390), "Location", fill=(0, 0, 0), font=font_bold)
    draw.text((300, 390), "Expected (mm)", fill=(0, 0, 0), font=font_bold)
    draw.text((500, 390), "Actual (mm)", fill=(0, 0, 0), font=font_bold)
    
    # Table Rows
    rows = [
        ("Top Dome", "12.0", "11.8"),
        ("Mid Shell", "15.0", "13.0"), # Thinned
        ("Bottom Flange", "18.0", "17.9")
    ]
    
    y = 420
    for r in rows:
        draw.rectangle([50, y, 750, y+40], outline=(0, 0, 0))
        draw.text((60, y+10), r[0], fill=(0, 0, 0), font=font_text)
        draw.text((300, y+10), r[1], fill=(0, 0, 0), font=font_text)
        draw.text((500, y+10), r[2], fill=(255, 0, 0) if float(r[2]) <= float(r[1])-1.5 else (0,0,0), font=font_text)
        y += 40
        
    # Signature
    draw.text((50, 600), "Inspector Signature: ___________________", fill=(0, 0, 0), font=font_text)
    
    img.save(filename)
    print(f"Created {filename}")

if __name__ == "__main__":
    create_mock_report()
