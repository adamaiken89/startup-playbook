import requests
from bs4 import BeautifulSoup
from ebooklib import epub
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import re
import hashlib

def download_image(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return BytesIO(response.content)
        return None
    except:
        return None

def create_cover():
    # Create a new image with a gradient background
    width, height = 1600, 2400
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)

    # Create gradient background
    for y in range(height):
        r = int(44 + (y / height) * 20)
        g = int(62 + (y / height) * 20)
        b = int(80 + (y / height) * 20)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # Add title
    title_text = "Sam Altman's\nPlaybook"
    try:
        # Try to use a nice font if available
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 120)
    except:
        # Fallback to default font
        font = ImageFont.load_default()

    # Calculate text position
    text_bbox = draw.textbbox((0, 0), title_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2

    # Add text with subtle shadow
    draw.text((x+2, y+2), title_text, font=font, fill=(30, 30, 30))
    draw.text((x, y), title_text, font=font, fill=(255, 255, 255))

    # Convert to bytes
    img_bytes = BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes

def download_playbook():
    url = "https://playbook.samaltman.com"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.text
    else:
        raise Exception(f"Failed to download content: {response.status_code}")

def clean_title(title):
    # Remove "Table of content" and any extra whitespace
    return re.sub(r'\s*Table of content\s*', '', title).strip()

def create_epub(html_content):
    # Create EPUB book
    book = epub.EpubBook()

    # Set metadata
    book.set_identifier('sam-altman-playbook')
    book.set_title('Sam Altman\'s Playbook')
    book.set_language('en')
    book.add_author('Sam Altman')

    # Add cover
    cover_image = create_cover()
    book.set_cover("cover.jpg", cover_image.getvalue())

    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # Clean up the content
    for script in soup.find_all('script'):
        script.decompose()
    for style in soup.find_all('style'):
        style.decompose()

    # Get the main content
    main_content = soup.find('main')
    if not main_content:
        main_content = soup.find('article')
    if not main_content:
        main_content = soup.find('div', class_='content')
    if not main_content:
        main_content = soup.find('body')

    if main_content:
        # Process images
        for img in main_content.find_all('img'):
            src = img.get('src')
            if src:
                if not src.startswith('http'):
                    if src.startswith('/'):
                        src = f"https://playbook.samaltman.com{src}"
                    else:
                        src = f"https://playbook.samaltman.com/{src}"

                img_data = download_image(src)
                if img_data:
                    # Generate a unique filename
                    img_hash = hashlib.md5(src.encode()).hexdigest()[:10]
                    img_ext = os.path.splitext(src)[1] or '.jpg'
                    img_filename = f'image_{img_hash}{img_ext}'

                    # Create image item
                    img_item = epub.EpubItem(
                        uid=f'image_{img_hash}',
                        file_name=f'images/{img_filename}',
                        media_type=f'image/{img_ext[1:]}',
                        content=img_data.getvalue()
                    )

                    # Add image to book
                    book.add_item(img_item)

                    # Update image src in HTML
                    img['src'] = f'images/{img_filename}'

        # Clean up section titles
        for h in main_content.find_all(['h1', 'h2', 'h3']):
            h.string = clean_title(h.get_text())

        # Create chapters based on main sections
        chapters = []
        toc = []

        # Define the sections we want in the TOC
        wanted_sections = [
            'Part I: The Idea',
            'Part II: A Great Team',
            'Part III: A Great Product',
            'Part IV: Great Execution',
            'Closing Thought',
            'Growth',
            'Focus & Intensity',
            'Jobs of the CEO',
            'Hiring & Managing',
            'Competitors',
            'Making Money',
            'Fundraising'
        ]

        # Find all headings
        headings = main_content.find_all(['h1', 'h2', 'h3'])
        current_chapter = None
        chapter_content = []

        for h in headings:
            title = clean_title(h.get_text())
            if title in wanted_sections:
                # If we have a previous chapter, save it
                if current_chapter:
                    chapter_html = '\n'.join(chapter_content)
                    current_chapter.content = f'''
                    <html xmlns="http://www.w3.org/1999/xhtml">
                    <head>
                        <title>{current_chapter.title}</title>
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                            h1, h2, h3 {{ color: #333; margin-top: 1.5em; }}
                            p {{ margin-bottom: 1em; }}
                            a {{ color: #0066cc; }}
                            img {{ max-width: 100%; height: auto; margin: 1em 0; }}
                        </style>
                    </head>
                    <body>
                        {chapter_html}
                    </body>
                    </html>
                    '''

                # Create new chapter
                chapter_id = f"chapter_{len(chapters)}"
                current_chapter = epub.EpubHtml(
                    title=title,
                    file_name=f'{chapter_id}.xhtml',
                    lang='en'
                )
                chapters.append(current_chapter)
                toc.append(current_chapter)
                chapter_content = []

            # Add content to current chapter
            if current_chapter:
                chapter_content.append(str(h))
                next_el = h.find_next_sibling()
                while next_el and next_el.name not in ['h1', 'h2', 'h3']:
                    chapter_content.append(str(next_el))
                    next_el = next_el.find_next_sibling()

        # Save the last chapter
        if current_chapter and chapter_content:
            chapter_html = '\n'.join(chapter_content)
            current_chapter.content = f'''
            <html xmlns="http://www.w3.org/1999/xhtml">
            <head>
                <title>{current_chapter.title}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
                    h1, h2, h3 {{ color: #333; margin-top: 1.5em; }}
                    p {{ margin-bottom: 1em; }}
                    a {{ color: #0066cc; }}
                    img {{ max-width: 100%; height: auto; margin: 1em 0; }}
                </style>
            </head>
            <body>
                {chapter_html}
            </body>
            </html>
            '''

        # Add all chapters to the book
        for chapter in chapters:
            book.add_item(chapter)

        # Create table of contents
        book.toc = toc

        # Add default NCX and Nav file
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        # Create spine
        book.spine = ['nav'] + chapters
    else:
        raise Exception("Could not find main content in the HTML")

    # Write EPUB file
    epub_path = 'sam_altman_playbook.epub'
    epub.write_epub(epub_path, book)
    return epub_path

def main():
    try:
        print("Downloading playbook content...")
        html_content = download_playbook()

        print("Creating EPUB...")
        epub_path = create_epub(html_content)

        print(f"Successfully created EPUB at: {epub_path}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
