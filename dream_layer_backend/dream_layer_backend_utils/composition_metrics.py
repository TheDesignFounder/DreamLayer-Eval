"""
Composition Metrics for DreamLayer
Combines YOLO object detection (prompt accuracy) with visual composition analysis
"""

import os
import re
import statistics
from typing import List, Dict, Any, Optional
import logging

import cv2
import numpy as np
import yaml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lazy imports for YOLO and NLTK (heavy dependencies)
_yolo_model = None
_yolo_loaded = False
_nltk_loaded = False
_lemmatizer = None






class CompositionMetricsCalculator:
    """Calculate both object detection and visual composition metrics"""

    def __init__(self, config_path: str = None):
        self.config = self._load_config(config_path)

    def _load_config(self, config_path: str = None) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if config_path is None:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(current_dir, '..', 'config', 'composition_config.yaml')

        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")

        # Default config
        return {
            "yolo": {"model": "yolov8n.pt", "conf_threshold": 0.25, "iou_threshold": 0.5, "max_detections": 100},
            "synonyms": {},
            "coco_classes": []
        }

    # ==================== YOLO OBJECT DETECTION ====================

    def extract_target_objects(self, prompt):
        from research.composition import interpret
        parsed = interpret(prompt)
        return {**parsed, 'target_objects': parsed['criteria'], 'mapped_objects': parsed['criteria']}

    def _word_to_number(self, word: str) -> int:
        """Convert word numbers to integers"""
        mapping = {"two": 2, "three": 3, "four": 4, "five": 5,
                   "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        return mapping.get(word.lower(), 1)

    def _map_to_coco_class(self, obj: str) -> Optional[str]:
        """Map object to COCO class using synonyms"""
        coco_classes = self.config.get("coco_classes", [])
        if obj in coco_classes:
            return obj

        for coco_class, synonyms in self.config.get("synonyms", {}).items():
            if obj in synonyms or obj == coco_class:
                return coco_class
        return None

    def detect_objects(self, image_path):
        from research.composition import detect
        return detect(image_path, self.config.get('yolo', {}).get('model'), self.config.get('yolo', {}).get('conf_threshold', .25))[0]

    def detect_objects_batch(self, image_paths, batch_size=16):
        return [self.detect_objects(p) for p in image_paths]

    def calculate_object_metrics(self, prompt, image_path):
        from research.composition import interpret, detect, evaluate_criteria
        parsed = interpret(prompt)
        try:
            from PIL import Image
            with Image.open(image_path) as image:
                image.verify()
            if not parsed['criteria']:
                output = evaluate_criteria([], [])
            else:
                weights = self.config.get('yolo', {}).get('model')
                detections, provenance = detect(image_path, weights, self.config.get('yolo', {}).get('conf_threshold', .25))
                classes = provenance['classes']
                output = evaluate_criteria(parsed['criteria'], detections, vocabulary=list(classes.values()) if isinstance(classes, dict) else classes)
                output['detector'] = provenance
        except ImportError as exc:
            output = {'status': 'unavailable_dependency', 'score': None, 'reason': str(exc)}
        except Exception as exc:
            output = {'status': 'failed_evaluation', 'score': None, 'reason': str(exc)}
        return {'object_precision': None, 'object_recall': None, 'object_f1': None,
                'macro_precision': None, 'macro_recall': None, 'macro_f1': None,
                'criterion_pass_rate': output['score'], 'object_criteria_result': output,
                'target_objects': parsed['criteria'], 'detected_objects': output.get('detected_objects', {}),
                'missing_objects': {}, 'per_class_metrics': {}, 'metric_id': 'object_criteria', 'metric_version': '1.0.0'}

    # ==================== VISUAL COMPOSITION ANALYSIS ====================

    def calculate_rule_of_thirds(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze how well the image follows the rule of thirds.
        Returns score 0-1 (higher = better adherence to rule of thirds)
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            height, width = gray.shape

            # Define rule of thirds lines (1/3 and 2/3 positions)
            h_lines = [height // 3, 2 * height // 3]
            v_lines = [width // 3, 2 * width // 3]

            # Power points (intersections)
            power_points = [(v, h) for h in h_lines for v in v_lines]

            # Detect edges to find areas of interest
            edges = cv2.Canny(gray, 50, 150)

            # Calculate edge density near power points and thirds lines
            margin = min(width, height) // 10

            total_score = 0.0

            # Score power points
            for x, y in power_points:
                y1, y2 = max(0, y - margin), min(height, y + margin)
                x1, x2 = max(0, x - margin), min(width, x + margin)
                region = edges[y1:y2, x1:x2]
                if region.size > 0:
                    density = np.mean(region) / 255.0
                    total_score += density

            # Normalize (4 power points)
            power_point_score = total_score / 4.0

            # Score edge alignment with thirds lines
            line_score = 0.0
            line_margin = margin // 2

            # Horizontal lines
            for h in h_lines:
                y1, y2 = max(0, h - line_margin), min(height, h + line_margin)
                region = edges[y1:y2, :]
                if region.size > 0:
                    line_score += np.mean(region) / 255.0

            # Vertical lines
            for v in v_lines:
                x1, x2 = max(0, v - line_margin), min(width, v + line_margin)
                region = edges[:, x1:x2]
                if region.size > 0:
                    line_score += np.mean(region) / 255.0

            line_score = line_score / 4.0  # 4 lines total

            # Combined score (weight power points more)
            final_score = 0.6 * power_point_score + 0.4 * line_score

            return {
                "rule_of_thirds_score": min(1.0, final_score * 3),  # Scale up for interpretability
                "power_point_score": min(1.0, power_point_score * 3),
                "line_alignment_score": min(1.0, line_score * 3)
            }
        except Exception as e:
            logger.error(f"Error calculating rule of thirds: {e}")
            return {"rule_of_thirds_score": None, "power_point_score": None, "line_alignment_score": None}

    def calculate_symmetry(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze horizontal and vertical symmetry.
        Returns score 0-1 (higher = more symmetrical)
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            gray = gray.astype(np.float32)
            height, width = gray.shape

            # Horizontal symmetry (flip left-right)
            left_half = gray[:, :width // 2]
            right_half = cv2.flip(gray[:, width - width // 2:], 1)

            # Ensure same size
            min_w = min(left_half.shape[1], right_half.shape[1])
            left_half = left_half[:, :min_w]
            right_half = right_half[:, :min_w]

            h_diff = np.abs(left_half - right_half)
            h_symmetry = 1.0 - (np.mean(h_diff) / 255.0)

            # Vertical symmetry (flip top-bottom)
            top_half = gray[:height // 2, :]
            bottom_half = cv2.flip(gray[height - height // 2:, :], 0)

            min_h = min(top_half.shape[0], bottom_half.shape[0])
            top_half = top_half[:min_h, :]
            bottom_half = bottom_half[:min_h, :]

            v_diff = np.abs(top_half - bottom_half)
            v_symmetry = 1.0 - (np.mean(v_diff) / 255.0)

            # Overall symmetry (max of both - images usually have one dominant axis)
            overall = max(h_symmetry, v_symmetry)

            return {
                "symmetry_score": overall,
                "horizontal_symmetry": h_symmetry,
                "vertical_symmetry": v_symmetry
            }
        except Exception as e:
            logger.error(f"Error calculating symmetry: {e}")
            return {"symmetry_score": None, "horizontal_symmetry": None, "vertical_symmetry": None}

    def calculate_visual_balance(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze visual weight distribution across quadrants.
        Returns score 0-1 (higher = better balanced)
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            height, width = gray.shape

            # Split into quadrants
            mid_h, mid_w = height // 2, width // 2
            quadrants = [
                gray[:mid_h, :mid_w],      # Top-left
                gray[:mid_h, mid_w:],      # Top-right
                gray[mid_h:, :mid_w],      # Bottom-left
                gray[mid_h:, mid_w:]       # Bottom-right
            ]

            # Calculate "visual weight" (intensity + edge density)
            weights = []
            for q in quadrants:
                intensity = np.mean(q) / 255.0
                edges = cv2.Canny(q.astype(np.uint8), 50, 150)
                edge_density = np.mean(edges) / 255.0
                weights.append(0.5 * intensity + 0.5 * edge_density)

            # Calculate balance (lower variance = better balance)
            variance = np.var(weights)
            balance_score = 1.0 - min(1.0, variance * 10)  # Scale variance

            return {
                "balance_score": balance_score,
                "quadrant_weights": weights
            }
        except Exception as e:
            logger.error(f"Error calculating visual balance: {e}")
            return {"balance_score": None, "quadrant_weights": None}

    def calculate_edge_distribution(self, image: np.ndarray) -> Dict[str, float]:
        """
        Analyze edge distribution - good images often have edges leading to focal points.
        """
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            height, width = gray.shape

            edges = cv2.Canny(gray, 50, 150)

            # Calculate edge density in center vs periphery
            center_margin = min(width, height) // 4
            center = edges[center_margin:height-center_margin, center_margin:width-center_margin]

            total_edges = np.sum(edges > 0)
            center_edges = np.sum(center > 0)

            if total_edges > 0:
                center_ratio = center_edges / total_edges
            else:
                center_ratio = 0.5

            # Good composition often has moderate center focus (not too much, not too little)
            # Optimal is around 0.3-0.5 (some center focus but not all)
            optimal_ratio = 0.4
            focus_score = 1.0 - abs(center_ratio - optimal_ratio) * 2
            focus_score = max(0, min(1, focus_score))

            return {
                "edge_focus_score": focus_score,
                "center_edge_ratio": center_ratio,
                "total_edge_density": np.mean(edges) / 255.0
            }
        except Exception as e:
            logger.error(f"Error calculating edge distribution: {e}")
            return {"edge_focus_score": None, "center_edge_ratio": None, "total_edge_density": None}

    def calculate_visual_composition(self, image_path: str) -> Dict[str, Any]:
        """Calculate all visual composition metrics for an image"""
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return self._empty_visual_metrics()

        try:
            image = cv2.imread(image_path)
            if image is None:
                logger.error(f"Failed to load image: {image_path}")
                return self._empty_visual_metrics()

            thirds = self.calculate_rule_of_thirds(image)
            symmetry = self.calculate_symmetry(image)
            balance = self.calculate_visual_balance(image)
            edges = self.calculate_edge_distribution(image)

            # Calculate overall composition score (weighted average)
            scores = []
            weights = []

            if thirds["rule_of_thirds_score"] is not None:
                scores.append(thirds["rule_of_thirds_score"])
                weights.append(0.3)
            if symmetry["symmetry_score"] is not None:
                scores.append(symmetry["symmetry_score"])
                weights.append(0.2)
            if balance["balance_score"] is not None:
                scores.append(balance["balance_score"])
                weights.append(0.25)
            if edges["edge_focus_score"] is not None:
                scores.append(edges["edge_focus_score"])
                weights.append(0.25)

            if scores and weights:
                total_weight = sum(weights)
                overall = sum(s * w for s, w in zip(scores, weights)) / total_weight
            else:
                overall = None

            return {
                "composition_score": overall,
                **thirds,
                **symmetry,
                **balance,
                **edges
            }
        except Exception as e:
            logger.error(f"Error calculating visual composition: {e}")
            return self._empty_visual_metrics()

    def _empty_visual_metrics(self) -> Dict[str, Any]:
        """Return empty visual metrics structure"""
        return {
            "composition_score": None,
            "rule_of_thirds_score": None,
            "power_point_score": None,
            "line_alignment_score": None,
            "symmetry_score": None,
            "horizontal_symmetry": None,
            "vertical_symmetry": None,
            "balance_score": None,
            "quadrant_weights": None,
            "edge_focus_score": None,
            "center_edge_ratio": None,
            "total_edge_density": None
        }

    # ==================== COMBINED METRICS ====================

    def calculate_all_metrics(self, prompt: str, image_path: str) -> Dict[str, Any]:
        """Calculate both object detection and visual composition metrics"""
        object_metrics = self.calculate_object_metrics(prompt, image_path)
        visual_metrics = self.calculate_visual_composition(image_path)

        return {
            **object_metrics,
            **visual_metrics
        }

    def calculate_all_metrics_batch(self, prompts, image_paths, batch_size=16):
        if len(prompts) != len(image_paths):
            raise ValueError('prompts and image_paths must have the same length')
        return [self.calculate_all_metrics(p, f) for p, f in zip(prompts, image_paths)]

    def _compute_object_metrics_from_detections(self, target_objects, detections):
        from research.composition import evaluate_criteria
        if not isinstance(target_objects, list):
            raise ValueError('Explicit structured criteria required; legacy count dictionaries are ambiguous')
        return evaluate_criteria(target_objects, detections)


# Singleton instance
_calculator = None

def get_composition_calculator() -> CompositionMetricsCalculator:
    """Get or create singleton calculator instance"""
    global _calculator
    if _calculator is None:
        _calculator = CompositionMetricsCalculator()
    return _calculator


def calculate_composition_metrics(prompt: str, image_path: str) -> Dict[str, Any]:
    """Convenience function to calculate all composition metrics"""
    calculator = get_composition_calculator()
    return calculator.calculate_all_metrics(prompt, image_path)


def calculate_composition_metrics_batch(
    prompts: List[str],
    image_paths: List[str],
    batch_size: int = 16
) -> List[Dict[str, Any]]:
    """
    Convenience function to calculate composition metrics for multiple images.

    Args:
        prompts: List of prompts (one per image)
        image_paths: List of image file paths
        batch_size: Batch size for YOLO inference (default: 16)

    Returns:
        List of metric dictionaries, one per image
    """
    calculator = get_composition_calculator()
    return calculator.calculate_all_metrics_batch(prompts, image_paths, batch_size)
