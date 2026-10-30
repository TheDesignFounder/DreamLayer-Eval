"""
Aesthetic Quality Metrics for DreamLayer - Phase 5
Implements LAION Aesthetic Predictor, Color Harmony Analysis, and Technical Quality Checks.
Custom color/technical heuristics, separate from task success.
"""

import os
import statistics
from typing import Dict, Any, Optional, List, Tuple
from urllib.request import urlretrieve
import logging

try:
    import cv2
except ImportError:
    cv2 = None
import numpy as np
try:
    import torch
    from transformers import CLIPProcessor, CLIPModel
except ImportError:
    torch = CLIPProcessor = CLIPModel = None
from PIL import Image

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy loaded models
_aesthetic_model = None
_aesthetic_model_loaded = False
_clip_model = None
_clip_processor = None


def _get_cache_dir() -> str:
    """Get or create cache directory for aesthetic models"""
    cache_dir = os.path.join(os.path.dirname(__file__), '..', 'data', 'models')
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def _ensure_aesthetic_model() -> bool:
    """
    Lazy load LAION aesthetic predictor model.
    Uses transformers CLIP for embeddings + linear regression for aesthetic score.
    """
    global _aesthetic_model, _aesthetic_model_loaded, _clip_model, _clip_processor

    if _aesthetic_model_loaded:
        return _aesthetic_model is not None

    try:
        device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"

        # Load CLIP model using transformers (consistent with clip_score_metrics.py)
        logger.info(f"Loading CLIP model for aesthetics on {device}")
        _clip_model = CLIPModel.from_pretrained("openai/clip-vit-large-patch14", local_files_only=True)
        _clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-large-patch14", local_files_only=True)
        _clip_model.eval()

        if device == "cuda":
            _clip_model = _clip_model.cuda()

        # Download and load aesthetic predictor linear model
        cache_dir = _get_cache_dir()
        model_path = os.path.join(cache_dir, "sa_0_4_vit_l_14_linear.pth")

        if not os.path.exists(model_path):
            model_url = "https://github.com/LAION-AI/aesthetic-predictor/blob/main/sa_0_4_vit_l_14_linear.pth?raw=true"
            logger.info(f"Downloading LAION aesthetic model to {model_path}")
            raise ImportError('Aesthetic weights unavailable; provision explicitly')

        # Load linear model (768 -> 1 for ViT-L/14)
        _aesthetic_model = torch.nn.Linear(768, 1)
        state_dict = torch.load(model_path, map_location=device, weights_only=True)
        _aesthetic_model.load_state_dict(state_dict)
        _aesthetic_model.to(device)
        _aesthetic_model.eval()

        _aesthetic_model_loaded = True
        logger.info("LAION aesthetic model loaded successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to load aesthetic model: {e}")
        _aesthetic_model_loaded = True  # Mark as attempted
        return False


class AestheticMetricsCalculator:
    """Calculate aesthetic quality metrics for images"""

    def __init__(self):
        self.device = "cuda" if torch is not None and torch.cuda.is_available() else "cpu"

    # ==================== LAION AESTHETIC PREDICTOR ====================

    def calculate_aesthetic_score(self, image_path: str) -> Optional[float]:
        """
        Calculate LAION aesthetic score (raw predictor output, unbounded).
        Higher scores indicate more aesthetically pleasing images.
        """
        if not _ensure_aesthetic_model():
            logger.warning("Aesthetic model not available")
            return None

        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return None

        try:
            # Load and preprocess image
            image = Image.open(image_path).convert('RGB')

            # Process image using transformers CLIP processor
            inputs = _clip_processor(images=[image], return_tensors="pt")

            # Move to correct device
            if self.device == "cuda" and next(_clip_model.parameters()).is_cuda:
                inputs = {k: v.cuda() if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}

            # Get CLIP image embeddings
            with torch.no_grad():
                image_features = _clip_model.get_image_features(**inputs)
                # Normalize features (L2 norm)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                # Get aesthetic score
                aesthetic_score = _aesthetic_model(image_features.float()).item()

            # Preserve raw predictor output (model can occasionally output outside this range)
            aesthetic_score = float(aesthetic_score)  # Preserve unbounded predictor output; no artificial clamp.

            logger.debug(f"Aesthetic score for {image_path}: {aesthetic_score:.2f}")
            return aesthetic_score

        except Exception as e:
            logger.error(f"Error calculating aesthetic score: {e}")
            return None

    def calculate_aesthetic_score_batch(
        self,
        image_paths: List[str],
        batch_size: int = 16
    ) -> List[Optional[float]]:
        """
        Calculate LAION aesthetic scores for multiple images using batch inference.

        Args:
            image_paths: List of image file paths
            batch_size: Number of images to process at once (default: 16)

        Returns:
            List of aesthetic scores (raw predictor output, unbounded), None for failed images
        """
        if not _ensure_aesthetic_model():
            logger.warning("Aesthetic model not available")
            return [None] * len(image_paths)

        n_images = len(image_paths)
        if n_images == 0:
            return []

        results = [None] * n_images
        logger.info(f"Calculating aesthetic scores for {n_images} images (batch_size={batch_size})")

        try:
            # Process in batches
            for batch_start in range(0, n_images, batch_size):
                batch_end = min(batch_start + batch_size, n_images)
                batch_paths = image_paths[batch_start:batch_end]

                # Load images, track which ones succeeded
                images = []
                valid_indices = []
                for i, path in enumerate(batch_paths):
                    if os.path.exists(path):
                        try:
                            img = Image.open(path).convert('RGB')
                            images.append(img)
                            valid_indices.append(batch_start + i)
                        except Exception as e:
                            logger.warning(f"Failed to load image {path}: {e}")
                    else:
                        logger.warning(f"Image not found: {path}")

                if not images:
                    continue

                # Process batch through CLIP
                inputs = _clip_processor(images=images, return_tensors="pt")

                # Move to correct device
                if self.device == "cuda" and next(_clip_model.parameters()).is_cuda:
                    inputs = {k: v.cuda() if isinstance(v, torch.Tensor) else v for k, v in inputs.items()}

                # Get CLIP embeddings and aesthetic scores
                with torch.no_grad():
                    image_features = _clip_model.get_image_features(**inputs)
                    # Normalize features (L2 norm)
                    image_features = image_features / image_features.norm(dim=-1, keepdim=True)
                    # Get aesthetic scores for batch
                    scores = _aesthetic_model(image_features.float()).squeeze(-1)

                    # Handle single image case
                    if scores.dim() == 0:
                        scores = scores.unsqueeze(0)

                    scores = scores.cpu().tolist()

                # Store results
                for idx, score in zip(valid_indices, scores):
                    # Preserve raw predictor output
                    results[idx] = float(score)

            logger.info(f"Completed aesthetic scores for {sum(1 for r in results if r is not None)} images")
            return results

        except Exception as e:
            logger.error(f"Error in batch aesthetic scoring: {e}")
            return [None] * n_images

    # ==================== COLOR HARMONY ANALYSIS ====================

    def calculate_color_harmony(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze color harmony of the image.
        Evaluates color relationships based on color theory principles.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return self._empty_color_metrics()

        try:
            image = cv2.imread(image_path)
            if image is None:
                return self._empty_color_metrics()

            # Convert to HSV for color analysis
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

            # Extract dominant colors using k-means clustering
            dominant_colors = self._extract_dominant_colors(hsv, n_colors=5)

            # Calculate harmony scores
            complementary_score = self._check_complementary(dominant_colors)
            analogous_score = self._check_analogous(dominant_colors)
            triadic_score = self._check_triadic(dominant_colors)

            # Color variety (how diverse the palette is)
            color_variety = self._calculate_color_variety(dominant_colors)

            # Saturation balance (mix of saturated and muted colors)
            saturation_balance = self._calculate_saturation_balance(hsv)

            # Value contrast (light/dark balance)
            value_contrast = self._calculate_value_contrast(hsv)

            # Overall harmony score (weighted combination)
            harmony_scores = [complementary_score, analogous_score, triadic_score]
            best_harmony = max(harmony_scores)

            overall_harmony = (
                0.4 * best_harmony +
                0.2 * color_variety +
                0.2 * saturation_balance +
                0.2 * value_contrast
            )

            return {
                "color_harmony_score": overall_harmony,
                "complementary_harmony": complementary_score,
                "analogous_harmony": analogous_score,
                "triadic_harmony": triadic_score,
                "color_variety": color_variety,
                "saturation_balance": saturation_balance,
                "value_contrast": value_contrast,
                "dominant_hues": [int(c[0]) for c in dominant_colors]  # Hue values 0-179
            }

        except Exception as e:
            logger.error(f"Error calculating color harmony: {e}")
            return self._empty_color_metrics()

    def _extract_dominant_colors(self, hsv_image: np.ndarray, n_colors: int = 5) -> List[Tuple[float, float, float]]:
        """Extract dominant colors using k-means clustering"""
        try:
            # Reshape for k-means
            pixels = hsv_image.reshape(-1, 3).astype(np.float32)

            # Sample for speed (max 10000 pixels)
            if len(pixels) > 10000:
                indices = np.random.choice(len(pixels), 10000, replace=False)
                pixels = pixels[indices]

            # K-means clustering
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
            _, labels, centers = cv2.kmeans(pixels, n_colors, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

            return [tuple(c) for c in centers]
        except Exception:
            return [(0, 0, 128)] * n_colors

    def _check_complementary(self, colors: List[Tuple[float, float, float]]) -> float:
        """Check for complementary color relationships (opposite on color wheel)"""
        if len(colors) < 2:
            return 0.0

        hues = [c[0] for c in colors if c[1] > 30]  # Only saturated colors
        if len(hues) < 2:
            return 0.5  # Neutral if mostly desaturated

        max_score = 0.0
        for i, h1 in enumerate(hues):
            for h2 in hues[i+1:]:
                # Complementary = 180 degrees apart (90 in OpenCV's 0-179 scale)
                diff = abs(h1 - h2)
                diff = min(diff, 180 - diff)  # Handle wraparound
                # Score peaks at 90 (complementary)
                score = 1.0 - abs(diff - 90) / 90
                max_score = max(max_score, score)

        return max_score

    def _check_analogous(self, colors: List[Tuple[float, float, float]]) -> float:
        """Check for analogous color relationships (adjacent on color wheel)"""
        if len(colors) < 2:
            return 0.0

        hues = [c[0] for c in colors if c[1] > 30]
        if len(hues) < 2:
            return 0.5

        # Analogous colors are within 30 degrees (15 in OpenCV scale)
        analogous_pairs = 0
        total_pairs = 0

        for i, h1 in enumerate(hues):
            for h2 in hues[i+1:]:
                diff = abs(h1 - h2)
                diff = min(diff, 180 - diff)
                total_pairs += 1
                if diff <= 20:  # ~40 degrees
                    analogous_pairs += 1

        return analogous_pairs / total_pairs if total_pairs > 0 else 0.0

    def _check_triadic(self, colors: List[Tuple[float, float, float]]) -> float:
        """Check for triadic color relationships (three colors 120 degrees apart)"""
        if len(colors) < 3:
            return 0.0

        hues = [c[0] for c in colors if c[1] > 30]
        if len(hues) < 3:
            return 0.3

        # Look for triadic pattern (60 degrees apart in OpenCV scale)
        max_score = 0.0
        for i, h1 in enumerate(hues):
            for j, h2 in enumerate(hues[i+1:], i+1):
                for h3 in hues[j+1:]:
                    diffs = sorted([
                        min(abs(h1 - h2), 180 - abs(h1 - h2)),
                        min(abs(h2 - h3), 180 - abs(h2 - h3)),
                        min(abs(h1 - h3), 180 - abs(h1 - h3))
                    ])
                    # Ideal triadic: all diffs ~60
                    avg_deviation = sum(abs(d - 60) for d in diffs) / 3
                    score = max(0, 1.0 - avg_deviation / 60)
                    max_score = max(max_score, score)

        return max_score

    def _calculate_color_variety(self, colors: List[Tuple[float, float, float]]) -> float:
        """Calculate how diverse the color palette is"""
        if len(colors) < 2:
            return 0.0

        hues = [c[0] for c in colors]
        saturations = [c[1] for c in colors]

        # Hue spread (standard deviation)
        hue_std = np.std(hues) / 90  # Normalize by max std

        # Saturation variety
        sat_std = np.std(saturations) / 128

        return min(1.0, (hue_std + sat_std) / 2 * 2)  # Scale up

    def _calculate_saturation_balance(self, hsv: np.ndarray) -> float:
        """Evaluate saturation distribution"""
        saturations = hsv[:, :, 1].flatten()
        mean_sat = np.mean(saturations)
        std_sat = np.std(saturations)

        # Good images have moderate saturation with some variety
        # Optimal: mean around 100, std around 50
        mean_score = 1.0 - abs(mean_sat - 100) / 155
        std_score = 1.0 - abs(std_sat - 50) / 100

        return max(0, min(1, (mean_score + std_score) / 2))

    def _calculate_value_contrast(self, hsv: np.ndarray) -> float:
        """Evaluate value (brightness) contrast"""
        values = hsv[:, :, 2].flatten()
        std_val = np.std(values)

        # Good contrast: std around 60-80
        optimal_std = 70
        score = 1.0 - abs(std_val - optimal_std) / optimal_std

        return max(0, min(1, score))

    def _empty_color_metrics(self) -> Dict[str, Any]:
        """Return empty color harmony metrics"""
        return {
            "color_harmony_score": None,
            "complementary_harmony": None,
            "analogous_harmony": None,
            "triadic_harmony": None,
            "color_variety": None,
            "saturation_balance": None,
            "value_contrast": None,
            "dominant_hues": None
        }

    # ==================== TECHNICAL QUALITY CHECKS ====================

    def calculate_technical_quality(self, image_path: str) -> Dict[str, Any]:
        """
        Analyze technical quality of the image.
        Checks sharpness, noise levels, and potential artifacts.
        """
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return self._empty_technical_metrics()

        try:
            image = cv2.imread(image_path)
            if image is None:
                return self._empty_technical_metrics()

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # Sharpness analysis
            sharpness_metrics = self._calculate_sharpness(gray)

            # Noise estimation
            noise_metrics = self._calculate_noise_level(gray)

            # Artifact detection
            artifact_metrics = self._detect_artifacts(image, gray)

            # Dynamic range
            dynamic_range = self._calculate_dynamic_range(gray)

            # Overall technical quality score
            overall_quality = (
                0.35 * sharpness_metrics["sharpness_score"] +
                0.25 * (1.0 - noise_metrics["noise_level"]) +
                0.25 * (1.0 - artifact_metrics["artifact_score"]) +
                0.15 * dynamic_range["dynamic_range_score"]
            )

            return {
                "technical_quality_score": overall_quality,
                **sharpness_metrics,
                **noise_metrics,
                **artifact_metrics,
                **dynamic_range
            }

        except Exception as e:
            logger.error(f"Error calculating technical quality: {e}")
            return self._empty_technical_metrics()

    def _calculate_sharpness(self, gray: np.ndarray) -> Dict[str, float]:
        """
        Calculate image sharpness using Laplacian variance.
        Higher variance = sharper image.
        """
        try:
            # Laplacian variance (standard sharpness measure)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian_var = laplacian.var()

            # Normalize to 0-1 scale (typical range 0-2000 for good images)
            sharpness_score = min(1.0, laplacian_var / 1000)

            # Sobel gradient magnitude
            sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            gradient_magnitude = np.sqrt(sobelx**2 + sobely**2)
            gradient_mean = np.mean(gradient_magnitude)

            # Normalize gradient (typical range 0-100)
            gradient_score = min(1.0, gradient_mean / 50)

            # Combined sharpness
            combined = 0.6 * sharpness_score + 0.4 * gradient_score

            return {
                "sharpness_score": combined,
                "laplacian_variance": laplacian_var,
                "gradient_magnitude": gradient_mean
            }
        except Exception:
            return {"sharpness_score": None, "laplacian_variance": None, "gradient_magnitude": None}

    def _calculate_noise_level(self, gray: np.ndarray) -> Dict[str, float]:
        """
        Estimate noise level using local variance in smooth regions.
        """
        try:
            # Apply slight blur to estimate noise-free version
            blurred = cv2.GaussianBlur(gray.astype(np.float32), (5, 5), 0)

            # Difference is approximate noise
            noise = gray.astype(np.float32) - blurred
            noise_std = np.std(noise)

            # Normalize (typical noise std 0-30)
            noise_level = min(1.0, noise_std / 30)

            # Also check high-frequency content ratio
            # High noise = more high-frequency content in smooth areas
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.mean(edges) / 255

            # High edge density in smooth areas suggests noise
            # Smooth areas defined by low gradient
            gradient = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
            smooth_mask = np.abs(gradient) < 10
            if np.sum(smooth_mask) > 0:
                smooth_noise = np.std(gray[smooth_mask])
                smooth_noise_level = min(1.0, smooth_noise / 40)
            else:
                smooth_noise_level = noise_level

            # Combined noise estimate
            combined_noise = 0.5 * noise_level + 0.5 * smooth_noise_level

            return {
                "noise_level": combined_noise,
                "noise_std": noise_std,
                "estimated_snr": max(1, 255 / (noise_std + 1))  # Signal-to-noise ratio
            }
        except Exception:
            return {"noise_level": None, "noise_std": None, "estimated_snr": None}

    def _detect_artifacts(self, image: np.ndarray, gray: np.ndarray) -> Dict[str, float]:
        """
        Detect common image generation artifacts:
        - Banding (gradient stepping)
        - Blocking (JPEG-like artifacts)
        - Color bleeding
        """
        try:
            height, width = gray.shape

            # Banding detection (look for horizontal/vertical lines in gradients)
            grad_h = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
            grad_v = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)

            # Strong horizontal lines in vertical gradient = banding
            h_lines = np.mean(np.abs(grad_h), axis=1)
            h_line_std = np.std(h_lines)
            banding_score = min(1.0, h_line_std / 20)

            # Blocking artifact detection (8x8 block boundaries from JPEG)
            block_size = 8
            block_boundaries_h = []
            block_boundaries_v = []

            for i in range(block_size, height - block_size, block_size):
                boundary_diff = np.mean(np.abs(gray[i, :].astype(float) - gray[i-1, :].astype(float)))
                internal_diff = np.mean(np.abs(gray[i-4, :].astype(float) - gray[i-5, :].astype(float)))
                if internal_diff > 0:
                    block_boundaries_h.append(boundary_diff / internal_diff)

            blocking_score = 0.0
            if block_boundaries_h:
                avg_ratio = np.mean(block_boundaries_h)
                blocking_score = min(1.0, max(0, (avg_ratio - 1) / 2))

            # Color bleeding (check for unnatural color transitions)
            if len(image.shape) == 3:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                hue_grad = cv2.Sobel(hsv[:, :, 0].astype(np.float32), cv2.CV_64F, 1, 0, ksize=3)
                sat_grad = cv2.Sobel(hsv[:, :, 1].astype(np.float32), cv2.CV_64F, 1, 0, ksize=3)

                # Sudden hue changes without corresponding saturation changes = bleeding
                hue_sharp = np.abs(hue_grad) > 30
                sat_stable = np.abs(sat_grad) < 10
                bleeding_pixels = np.sum(hue_sharp & sat_stable)
                bleeding_score = min(1.0, bleeding_pixels / (height * width) * 100)
            else:
                bleeding_score = 0.0

            # Overall artifact score (lower is better)
            overall_artifact = (banding_score + blocking_score + bleeding_score) / 3

            return {
                "artifact_score": overall_artifact,
                "banding_level": banding_score,
                "blocking_level": blocking_score,
                "color_bleeding_level": bleeding_score
            }
        except Exception:
            return {"artifact_score": None, "banding_level": None, "blocking_level": None, "color_bleeding_level": None}

    def _calculate_dynamic_range(self, gray: np.ndarray) -> Dict[str, float]:
        """Calculate dynamic range utilization"""
        try:
            min_val = np.min(gray)
            max_val = np.max(gray)
            range_used = max_val - min_val

            # Good images use most of the dynamic range (200+ out of 255)
            range_score = min(1.0, range_used / 200)

            # Also check histogram distribution
            hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
            hist = hist / hist.sum()

            # Entropy as measure of distribution (max ~8 for uniform)
            entropy = -np.sum(hist[hist > 0] * np.log2(hist[hist > 0]))
            entropy_score = min(1.0, entropy / 7)

            combined = 0.5 * range_score + 0.5 * entropy_score

            return {
                "dynamic_range_score": combined,
                "intensity_range": range_used,
                "histogram_entropy": entropy
            }
        except Exception:
            return {"dynamic_range_score": None, "intensity_range": None, "histogram_entropy": None}

    def _empty_technical_metrics(self) -> Dict[str, Any]:
        """Return empty technical quality metrics"""
        return {
            "technical_quality_score": None,
            "sharpness_score": None,
            "laplacian_variance": None,
            "gradient_magnitude": None,
            "noise_level": None,
            "noise_std": None,
            "estimated_snr": None,
            "artifact_score": None,
            "banding_level": None,
            "blocking_level": None,
            "color_bleeding_level": None,
            "dynamic_range_score": None,
            "intensity_range": None,
            "histogram_entropy": None
        }

    # ==================== COMBINED METRICS ====================

    def calculate_all_aesthetic_metrics(self, image_path: str) -> Dict[str, Any]:
        """Calculate all aesthetic quality metrics for an image"""
        results = {}

        # LAION Aesthetic Score
        aesthetic_score = self.calculate_aesthetic_score(image_path)
        if aesthetic_score is not None:
            results["aesthetics_score"] = aesthetic_score

        # Color Harmony
        color_metrics = self.calculate_color_harmony(image_path)
        results.update(color_metrics)

        # Technical Quality
        technical_metrics = self.calculate_technical_quality(image_path)
        results.update(technical_metrics)

        results["overall_aesthetic_quality"] = None
        results["metric_version"] = "custom-aesthetic-heuristics-v2"
        results["limitation"] = "Uncalibrated color/technical heuristics; no overall quality or task-success score"

        return results

    def calculate_all_aesthetic_metrics_batch(
        self,
        image_paths: List[str],
        batch_size: int = 16
    ) -> List[Dict[str, Any]]:
        """
        Calculate all aesthetic metrics for multiple images using batch processing.

        Args:
            image_paths: List of image file paths
            batch_size: Batch size for CLIP inference (default: 16)

        Returns:
            List of metric dictionaries, one per image
        """
        n_images = len(image_paths)
        if n_images == 0:
            return []

        logger.info(f"Calculating aesthetic metrics for {n_images} images (batch_size={batch_size})")

        # Step 1: Batch LAION aesthetic scores (the GPU-bound part)
        aesthetic_scores = self.calculate_aesthetic_score_batch(image_paths, batch_size=batch_size)

        # Step 2: Calculate color and technical metrics (CPU-bound, fast)
        results = []
        for i, image_path in enumerate(image_paths):
            metrics = {}

            # Add aesthetic score
            if aesthetic_scores[i] is not None:
                metrics["aesthetics_score"] = aesthetic_scores[i]

            # Color Harmony (OpenCV, ~30ms per image)
            color_metrics = self.calculate_color_harmony(image_path)
            metrics.update(color_metrics)

            # Technical Quality (OpenCV, ~20ms per image)
            technical_metrics = self.calculate_technical_quality(image_path)
            metrics.update(technical_metrics)

            metrics["overall_aesthetic_quality"] = None
            metrics["metric_version"] = "custom-aesthetic-heuristics-v2"

            results.append(metrics)

        logger.info(f"Completed aesthetic metrics for {n_images} images")
        return results


# Singleton instance
_calculator = None


def get_aesthetic_calculator() -> AestheticMetricsCalculator:
    """Get or create singleton calculator instance"""
    global _calculator
    if _calculator is None:
        _calculator = AestheticMetricsCalculator()
    return _calculator


def calculate_aesthetic_metrics(image_path: str) -> Dict[str, Any]:
    """Convenience function to calculate all aesthetic metrics"""
    calculator = get_aesthetic_calculator()
    return calculator.calculate_all_aesthetic_metrics(image_path)


def calculate_aesthetic_metrics_batch(
    image_paths: List[str],
    batch_size: int = 16
) -> List[Dict[str, Any]]:
    """
    Convenience function to calculate aesthetic metrics for multiple images.

    Args:
        image_paths: List of image file paths
        batch_size: Batch size for CLIP inference (default: 16)

    Returns:
        List of metric dictionaries, one per image
    """
    calculator = get_aesthetic_calculator()
    return calculator.calculate_all_aesthetic_metrics_batch(image_paths, batch_size)
