"""
Roboflow Detection Module - Handles object detection via Roboflow API
"""
import logging
import os
import time
import tempfile
import threading
import hashlib
from typing import Optional, Dict, List, Tuple
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image
from roboflow import Roboflow

from config import DEFAULT_CONFIDENCE, MAX_WORKERS, MAX_CACHE_SIZE, TILE_SIZE

logger = logging.getLogger(__name__)


class TileCache:
    """Cache for tile processing results to avoid reprocessing identical tiles (LRU with max size)"""
    
    def __init__(self, max_size: int = MAX_CACHE_SIZE):
        self.cache = OrderedDict()
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
        self.lock = threading.Lock()
    
    def get_tile_hash(self, tile_image: Image.Image) -> str:
        """Generate MD5 hash for a tile image"""
        img_bytes = tile_image.tobytes()
        return hashlib.md5(img_bytes).hexdigest()
    
    def get(self, tile_hash: str) -> Optional[Dict]:
        """Get cached result for a tile and update LRU order"""
        with self.lock:
            if tile_hash in self.cache:
                self.hits += 1
                self.cache.move_to_end(tile_hash)  # Mark as recently used
                return self.cache[tile_hash]
            self.misses += 1
            return None
    
    def set(self, tile_hash: str, result: Dict):
        """Cache result for a tile, evict LRU if over max size"""
        with self.lock:
            self.cache[tile_hash] = result
            self.cache.move_to_end(tile_hash)
            if len(self.cache) > self.max_size:
                self.cache.popitem(last=False)  # Remove least recently used
    
    def clear(self):
        """Clear the cache"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'hits': self.hits,
                'misses': self.misses,
                'total': total,
                'hit_rate': hit_rate,
                'size': len(self.cache)
            }


class RoboflowDetector:
    """Roboflow API wrapper with caching and parallel processing"""
    
    def __init__(self, api_key: str, workspace: str, project: str, version: int):
        self.api_key = api_key
        self.workspace = workspace
        self.project = project
        self.version = version
        self.model = None
        self.cache = TileCache()
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize Roboflow model with retries and validation"""
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Validate inputs
                if not self.api_key or not isinstance(self.api_key, str):
                    raise ValueError("Invalid API key")
                
                logger.info(f"Initializing Roboflow (attempt {attempt + 1}/{max_retries})")
                logger.info(f"Workspace: {self.workspace}, Project: {self.project}, Version: {self.version}")
                
                # Create client
                rf = Roboflow(api_key=self.api_key)
                logger.info("Roboflow client created")
                
                # Test API key
                try:
                    workspace = rf.workspace(self.workspace)
                    logger.info("API key validated successfully")
                except Exception as api_err:
                    logger.error(f"API key validation failed: {str(api_err)}")
                    raise ValueError("Invalid API key or permissions") from api_err
                
                # Get project
                project = workspace.project(self.project)
                if not project:
                    raise ValueError(f"Project not found: {self.project}")
                logger.info(f"Project accessed: {self.project}")
                
                # Get model version
                self.model = project.version(self.version).model
                if not self.model:
                    raise ValueError(f"Model version not found: {self.version}")
                
                # Validate model
                if not hasattr(self.model, 'predict'):
                    raise ValueError("Model loaded but predict method not found")
                
                logger.info(f"✅ Model initialized: {self.workspace}/{self.project}/{self.version}")
                return
                
            except Exception as e:
                logger.error(f"❌ Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("All initialization attempts failed")
                    raise RuntimeError(f"Failed to initialize Roboflow after {max_retries} attempts") from e
    
    def detect_on_tile(self, tile_image: Image.Image, confidence: float = DEFAULT_CONFIDENCE,
                    use_cache: bool = True) -> Optional[Dict]:
        """
        Run detection on a single tile with optional caching
        
        Args:
            tile_image: PIL Image tile
            confidence: Detection confidence threshold
            use_cache: Whether to use cached results
        
        Returns:
            Predictions dict or None if error
        """
        # Check cache first
        if use_cache:
            tile_hash = self.cache.get_tile_hash(tile_image)
            cached_result = self.cache.get(tile_hash)
            if cached_result is not None:
                return cached_result
        
        if not tile_image or not isinstance(tile_image, Image.Image):
            logger.error("Invalid tile image provided")
            return None
        
        try:
            # Save tile to temporary file (Roboflow requires file path)
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                tile_image.save(tmp_file.name, format='JPEG', quality=95)
                temp_path = tmp_file.name
            
            try:
                # Run prediction
                predictions = self.model.predict(temp_path, confidence=int(confidence * 100))
                result = predictions.json()
                
                # Cache result
                if use_cache:
                    tile_hash = self.cache.get_tile_hash(tile_image)
                    self.cache.set(tile_hash, result)
                
                return result
            finally:
                # Clean up temporary file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            logger.error(f"Error during detection: {str(e)}")
            return None
    
    def process_all_tiles_parallel(self, tiles: List[Dict], confidence: float = DEFAULT_CONFIDENCE,
                                        max_workers: int = MAX_WORKERS, use_cache: bool = True,
                                        early_stop_count: Optional[int] = None) -> Tuple[List[Dict], Dict]:
            """
            Process tiles in parallel with optional early stopping
            
            Args:
                tiles: List of tile dictionaries
                confidence: Detection confidence threshold
                max_workers: Number of parallel workers
                use_cache: Whether to use cached results
                early_stop_count: Stop after finding this many objects
            
            Returns:
                Tuple of (all_detections, processing_stats)
            """
            all_detections = []
            start_time = time.time()
            processed = 0
            early_stopped = False
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_tile = {
                    executor.submit(self.detect_on_tile, tile['image'], confidence, use_cache): tile
                    for tile in tiles
                }
                
                # Process completed tasks
                for future in as_completed(future_to_tile):
                    tile = future_to_tile[future]
                    processed += 1
                    
                    try:
                        predictions = future.result()
                        
                        if predictions and 'predictions' in predictions:
                            for pred in predictions['predictions']:
                                
                                # --- START: CORRECTED COORDINATE LOGIC ---
                                
                                # Your desired scale factor for "tighter" boxes
                                scale_factor = 1.0
                                
                                # The Roboflow package returns *pixel coordinates* relative
                                # to the tile image (e.g., 640x640).
                                # NO normalization (/ 100.0) or ( * TILE_SIZE) is needed here.
                                
                                # These are the center (x,y) and dimensions (w,h) *within the tile*
                                tile_center_x = pred['x']
                                tile_center_y = pred['y']
                                tile_width = pred['width']
                                tile_height = pred['height']

                                # Apply your desired 0.6 scaling to the *pixel dimensions*
                                scaled_width = max(20, int(tile_width * scale_factor))
                                scaled_height = max(20, int(tile_height * scale_factor))
                                
                                # Adjust to full image space by adding the tile's offset
                                # to the box's center coordinate within the tile.
                                pred['x'] = tile['x'] + tile_center_x
                                pred['y'] = tile['y'] + tile_center_y
                                pred['width'] = scaled_width
                                pred['height'] = scaled_height
                                
                                # --- END: CORRECTED COORDINATE LOGIC ---

                                pred['tile_id'] = tile['id']
                                all_detections.append(pred)
                        
                        # Check early stopping
                        if early_stop_count and len(all_detections) >= early_stop_count:
                            logger.info(f"Early stopping: Found {len(all_detections)} objects")
                            early_stopped = True
                            for f in future_to_tile:
                                if not f.done():
                                    f.cancel()
                            break
                    
                    except Exception as e:
                        logger.warning(f"Error processing tile {tile['id']}: {str(e)}")
            
            processing_time = time.time() - start_time
            cache_stats = self.cache.get_stats()
            
            stats = {
                'processed': processed,
                'total_time': processing_time,
                'cache_hits': cache_stats['hits'],
                'cache_misses': cache_stats['misses'],
                'cache_hit_rate': cache_stats['hit_rate'],
                'early_stopped': early_stopped,
                'objects_found': len(all_detections)
            }
            
            return all_detections, stats
    
    def process_all_tiles_sequential(self, tiles: List[Dict], confidence: float = DEFAULT_CONFIDENCE,
                                    use_cache: bool = True,
                                    early_stop_count: Optional[int] = None) -> Tuple[List[Dict], Dict]:
        """
        Process tiles sequentially with optional early stopping
        
        Args:
            tiles: List of tile dictionaries
            confidence: Detection confidence threshold
            use_cache: Whether to use cached results
            early_stop_count: Stop after finding this many objects
        
        Returns:
            Tuple of (all_detections, processing_stats)
        """
        all_detections = []
        start_time = time.time()
        processed = 0
        early_stopped = False
        
        for tile in tiles:
            try:
                predictions = self.detect_on_tile(tile['image'], confidence, use_cache)
                processed += 1
                
                if predictions and 'predictions' in predictions:
                    for pred in predictions['predictions']:
                        # Adjust coordinates to full image space
                        pred['x'] += tile['x']
                        pred['y'] += tile['y']
                        pred['tile_id'] = tile['id']
                        all_detections.append(pred)
                
                # Check early stopping
                if early_stop_count and len(all_detections) >= early_stop_count:
                    logger.info(f"Early stopping: Found {len(all_detections)} objects")
                    early_stopped = True
                    break
            
            except Exception as e:
                logger.warning(f"Error processing tile {tile['id']}: {str(e)}")
        
        processing_time = time.time() - start_time
        cache_stats = self.cache.get_stats()
        
        stats = {
            'processed': processed,
            'total_time': processing_time,
            'cache_hits': cache_stats['hits'],
            'cache_misses': cache_stats['misses'],
            'cache_hit_rate': cache_stats['hit_rate'],
            'early_stopped': early_stopped,
            'objects_found': len(all_detections)
        }
        
        return all_detections, stats
