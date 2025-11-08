"""
PDF Processing Module - Handles PDF to image conversion and tiling
"""
import logging
from typing import List, Tuple, Dict
import fitz  # PyMuPDF
from PIL import Image
import numpy as np

from config import DPI, TILE_SIZE, OVERLAP_PERCENT

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Handles PDF to image conversion and optimized tiling"""
    
    def __init__(self, dpi: int = DPI):
        self.dpi = dpi
    def extract_text_from_pdf(self, pdf_source):
        """
        Extract text content from each PDF page.
        Accepts either a filesystem path or raw PDF bytes.
        """
        try:
            # Determine whether it's a path or a file-like/bytes object
            if isinstance(pdf_source, (bytes, bytearray)):
                doc = fitz.open(stream=pdf_source, filetype="pdf")
            elif hasattr(pdf_source, "read"):  # e.g. Flask FileStorage
                doc = fitz.open(stream=pdf_source.read(), filetype="pdf")
            elif isinstance(pdf_source, str):
                doc = fitz.open(pdf_source)
            else:
                raise TypeError(f"Unsupported pdf_source type: {type(pdf_source)}")

            pages = []
            for i, page in enumerate(doc, start=1):
                pages.append({
                    "page_number": i,
                    "text": page.get_text()
                })
            doc.close()
            return pages

        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}", exc_info=True)
            return []
        
    def pdf_to_images(self, pdf_path: str, selected_pages: List[int] = None) -> List[Image.Image]:
        """
        Convert PDF to list of PIL Images
        
        Args:
            pdf_path: Path to PDF file
            selected_pages: Optional list of page numbers to process (1-indexed)
        
        Returns:
            List of PIL Image objects
        """
        try:
            logger.info(f"Opening PDF: {pdf_path}")
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            images = []
            
            # Determine which pages to process
            if selected_pages:
                pages_to_process = [p-1 for p in selected_pages if 1 <= p <= total_pages]
                logger.info(f"Processing selected pages: {[p+1 for p in pages_to_process]}")
            else:
                pages_to_process = range(total_pages)
                logger.info(f"Processing all {total_pages} pages")
            
            for page_num in pages_to_process:
                try:
                    page = doc[page_num]
                    logger.info(f"Processing page {page_num + 1}/{total_pages}")
                    
                    # Get page size and validate
                    page_size = page.rect.width * page.rect.height
                    if page_size == 0:
                        logger.warning(f"Page {page_num + 1} has zero size, skipping")
                        continue
                    
                    # Render page to image
                    mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                    try:
                        pix = page.get_pixmap(matrix=mat)
                        if not pix or pix.width == 0 or pix.height == 0:
                            logger.warning(f"Invalid pixmap on page {page_num + 1}, skipping")
                            continue
                        
                        # Convert to PIL Image
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                        images.append(img)
                        logger.info(f"Successfully processed page {page_num + 1} ({img.width}x{img.height})")
                    except Exception as render_err:
                        logger.error(f"Error rendering page {page_num + 1}: {str(render_err)}")
                        continue
                except Exception as page_err:
                    logger.error(f"Error processing page {page_num + 1}: {str(page_err)}")
                    continue
            
            doc.close()
            logger.info(f"Successfully converted {len(images)} pages")
            return images
            
        except Exception as e:
            logger.error(f"Error converting PDF to images: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def is_blank_tile(tile_image: Image.Image, threshold: float = 0.95, 
                     variance_threshold: float = 100) -> bool:
        """
        Check if a tile is mostly blank/empty
        
        Args:
            tile_image: PIL Image tile
            threshold: White pixel ratio threshold
            variance_threshold: Variance threshold for uniformity
        
        Returns:
            True if tile is blank
        """
        gray = tile_image.convert('L')
        np_img = np.array(gray)
        
        # Check white pixel ratio
        white_pixels = np.sum(np_img > 240)
        total_pixels = np_img.size
        white_ratio = white_pixels / total_pixels
        
        # Check variance (low variance = uniform/blank content)
        variance = np.var(np_img)
        
        return white_ratio > threshold or variance < variance_threshold
    
    @staticmethod
    def is_edge_tile(x: int, y: int, tile_size: int, img_width: int, 
                     img_height: int, margin: int = 50) -> bool:
        """
        Check if a tile is near the document edge
        
        Args:
            x, y: Tile position
            tile_size: Size of tile
            img_width, img_height: Image dimensions
            margin: Margin size in pixels
        
        Returns:
            True if tile is near edge
        """
        return (x < margin or 
                y < margin or 
                x + tile_size > img_width - margin or 
                y + tile_size > img_height - margin)
    
    @staticmethod
    def calculate_tile_complexity(tile_image: Image.Image) -> float:
        """
        Calculate complexity score for a tile
        Higher score = more content/edges = more likely to contain objects
        
        Args:
            tile_image: PIL Image tile
        
        Returns:
            Complexity score (float)
        """
        gray = tile_image.convert('L')
        np_img = np.array(gray)
        
        # Use edge detection as proxy for content complexity
        edges_h = np.abs(np.diff(np_img, axis=0)).sum()
        edges_v = np.abs(np.diff(np_img, axis=1)).sum()
        edges = edges_h + edges_v
        
        return edges / np_img.size
    
    def create_tiles(self, image: Image.Image, tile_size: int = TILE_SIZE,
                     overlap: float = OVERLAP_PERCENT,
                     skip_blank: bool = True,
                     skip_edges: bool = False,
                     edge_margin: int = 50,
                     blank_threshold: float = 0.95,
                     prioritize_complex: bool = True) -> Tuple[List[Dict], Dict]:
        """
        Create tiles from image with advanced filtering and prioritization
        
        Args:
            image: PIL Image to tile
            tile_size: Size of each tile
            overlap: Overlap percentage between tiles
            skip_blank: Skip mostly blank tiles
            skip_edges: Skip tiles near document edges
            edge_margin: Margin size for edge detection
            blank_threshold: Threshold for blank detection
            prioritize_complex: Sort tiles by complexity
        
        Returns:
            Tuple of (tiles list, statistics dict)
        """
        tiles = []
        img_width, img_height = image.size
        stride = int(tile_size * (1 - overlap))
        
        stats = {
            'total_created': 0,
            'blank_filtered': 0,
            'edge_filtered': 0,
            'kept': 0
        }
        
        tile_id = 0
        
        # Create main grid tiles
        for y in range(0, img_height - tile_size + 1, stride):
            for x in range(0, img_width - tile_size + 1, stride):
                stats['total_created'] += 1
                
                # Check if edge tile (skip if enabled)
                if skip_edges and self.is_edge_tile(x, y, tile_size, img_width, 
                                                     img_height, edge_margin):
                    stats['edge_filtered'] += 1
                    continue
                
                # Extract tile
                tile = image.crop((x, y, x + tile_size, y + tile_size))
                
                # Check if blank tile (skip if enabled)
                if skip_blank and self.is_blank_tile(tile, blank_threshold):
                    stats['blank_filtered'] += 1
                    continue
                
                # Calculate complexity for prioritization
                complexity = self.calculate_tile_complexity(tile) if prioritize_complex else 0
                
                tiles.append({
                    'id': tile_id,
                    'image': tile,
                    'x': x,
                    'y': y,
                    'width': tile_size,
                    'height': tile_size,
                    'complexity': complexity
                })
                tile_id += 1
                stats['kept'] += 1
        
        # Handle right edge tiles
        if img_width % stride != 0:
            x = img_width - tile_size
            for y in range(0, img_height - tile_size + 1, stride):
                if skip_edges and self.is_edge_tile(x, y, tile_size, img_width, 
                                                     img_height, edge_margin):
                    continue
                tile = image.crop((x, y, x + tile_size, y + tile_size))
                if skip_blank and self.is_blank_tile(tile, blank_threshold):
                    continue
                complexity = self.calculate_tile_complexity(tile) if prioritize_complex else 0
                tiles.append({
                    'id': tile_id,
                    'image': tile,
                    'x': x,
                    'y': y,
                    'width': tile_size,
                    'height': tile_size,
                    'complexity': complexity
                })
                tile_id += 1
                stats['kept'] += 1
        
        # Handle bottom edge tiles
        if img_height % stride != 0:
            y = img_height - tile_size
            for x in range(0, img_width - tile_size + 1, stride):
                if skip_edges and self.is_edge_tile(x, y, tile_size, img_width, 
                                                     img_height, edge_margin):
                    continue
                tile = image.crop((x, y, x + tile_size, y + tile_size))
                if skip_blank and self.is_blank_tile(tile, blank_threshold):
                    continue
                complexity = self.calculate_tile_complexity(tile) if prioritize_complex else 0
                tiles.append({
                    'id': tile_id,
                    'image': tile,
                    'x': x,
                    'y': y,
                    'width': tile_size,
                    'height': tile_size,
                    'complexity': complexity
                })
                tile_id += 1
                stats['kept'] += 1
        
        # Bottom-right corner
        if img_width % stride != 0 and img_height % stride != 0:
            x = img_width - tile_size
            y = img_height - tile_size
            if not (skip_edges and self.is_edge_tile(x, y, tile_size, img_width, 
                                                     img_height, edge_margin)):
                tile = image.crop((x, y, x + tile_size, y + tile_size))
                if not (skip_blank and self.is_blank_tile(tile, blank_threshold)):
                    complexity = self.calculate_tile_complexity(tile) if prioritize_complex else 0
                    tiles.append({
                        'id': tile_id,
                        'image': tile,
                        'x': x,
                        'y': y,
                        'width': tile_size,
                        'height': tile_size,
                        'complexity': complexity
                    })
                    stats['kept'] += 1
        
        # Sort by complexity if prioritization enabled
        if prioritize_complex and tiles:
            tiles.sort(key=lambda t: t['complexity'], reverse=True)
        
        return tiles, stats
