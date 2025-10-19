from typing import List, Dict, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from .pdf_extractor import LineData


@dataclass
class HeaderFooterResult:
    """Result of header/footer detection"""
    page_headers: Dict[int, List[int]]  # page -> list of line indices
    page_footers: Dict[int, List[int]]  # page -> list of line indices
    header_clusters: List[List[str]]    # clusters of similar header texts
    footer_clusters: List[List[str]]    # clusters of similar footer texts


class HeaderFooterDetector:
    """Detect repeating headers and footers using clustering and similarity"""
    
    def __init__(self, similarity_threshold: float = 0.85, min_cluster_size: int = 2):
        """
        Args:
            similarity_threshold: Minimum similarity for text shingle matching
            min_cluster_size: Minimum pages that must share text for it to be header/footer
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
    
    def detect_headers_footers(self, lines: List[LineData]) -> HeaderFooterResult:
        """Main method to detect headers and footers"""
        if not lines:
            return HeaderFooterResult({}, {}, [], [])
        
        # Group lines by page
        lines_by_page = self._group_by_page(lines)
        
        if len(lines_by_page) < self.min_cluster_size:
            # Not enough pages for meaningful header/footer detection
            return HeaderFooterResult({}, {}, [], [])
        
        # Extract potential headers (top 10%) and footers (bottom 10%)
        header_candidates = self._extract_header_candidates(lines_by_page)
        footer_candidates = self._extract_footer_candidates(lines_by_page)
        
        # Cluster similar texts
        header_clusters = self._cluster_similar_texts(header_candidates)
        footer_clusters = self._cluster_similar_texts(footer_candidates)
        
        # Map clusters back to page and line indices
        page_headers = self._map_clusters_to_pages(header_clusters, lines, is_header=True)
        page_footers = self._map_clusters_to_pages(footer_clusters, lines, is_header=False)
        
        return HeaderFooterResult(
            page_headers=page_headers,
            page_footers=page_footers,
            header_clusters=header_clusters,
            footer_clusters=footer_clusters
        )
    
    def mark_header_footer_lines(self, lines: List[LineData]) -> List[LineData]:
        """Mark lines with PAGE_HEADER or PAGE_FOOTER labels"""
        result = self.detect_headers_footers(lines)
        
        # Create a mapping of line index to label
        line_labels = {}
        
        for page_num, line_indices in result.page_headers.items():
            for line_idx in line_indices:
                line_labels[line_idx] = "PAGE_HEADER"
        
        for page_num, line_indices in result.page_footers.items():
            for line_idx in line_indices:
                line_labels[line_idx] = "PAGE_FOOTER"
        
        # Create new lines with labels
        marked_lines = []
        for i, line in enumerate(lines):
            if i in line_labels:
                # Add label to text
                new_text = f"[{line_labels[i]}] {line.text}"
                new_line = LineData(
                    page=line.page,
                    text=new_text,
                    xLeft=line.xLeft,
                    xRight=line.xRight,
                    yNorm=line.yNorm,
                    fontSize=line.fontSize,
                    isBold=line.isBold,
                    hasText=line.hasText,
                    source=line.source
                )
                marked_lines.append(new_line)
            else:
                marked_lines.append(line)
        
        return marked_lines
    
    def _group_by_page(self, lines: List[LineData]) -> Dict[int, List[Tuple[int, LineData]]]:
        """Group lines by page number with their original indices"""
        by_page = defaultdict(list)
        for idx, line in enumerate(lines):
            by_page[line.page].append((idx, line))
        return dict(by_page)
    
    def _extract_header_candidates(self, lines_by_page: Dict[int, List[Tuple[int, LineData]]]) -> Dict[str, List[Tuple[int, int, LineData]]]:
        """Extract top 10% lines from each page as header candidates"""
        candidates = defaultdict(list)
        
        for page_num, page_lines in lines_by_page.items():
            if not page_lines:
                continue
            
            # Sort by yNorm descending (top of page first)
            sorted_lines = sorted(page_lines, key=lambda x: x[1].yNorm, reverse=True)
            
            # Take top 10%
            top_10_percent = max(1, len(sorted_lines) // 10)
            header_lines = sorted_lines[:top_10_percent]
            
            for original_idx, line in header_lines:
                # Normalize text for clustering
                normalized_text = self._normalize_text(line.text)
                if normalized_text:
                    candidates[normalized_text].append((original_idx, page_num, line))
        
        return candidates
    
    def _extract_footer_candidates(self, lines_by_page: Dict[int, List[Tuple[int, LineData]]]) -> Dict[str, List[Tuple[int, int, LineData]]]:
        """Extract bottom 10% lines from each page as footer candidates"""
        candidates = defaultdict(list)
        
        for page_num, page_lines in lines_by_page.items():
            if not page_lines:
                continue
            
            # Sort by yNorm ascending (bottom of page first)
            sorted_lines = sorted(page_lines, key=lambda x: x[1].yNorm)
            
            # Take bottom 10%
            bottom_10_percent = max(1, len(sorted_lines) // 10)
            footer_lines = sorted_lines[:bottom_10_percent]
            
            for original_idx, line in footer_lines:
                # Normalize text for clustering
                normalized_text = self._normalize_text(line.text)
                if normalized_text:
                    candidates[normalized_text].append((original_idx, page_num, line))
        
        return candidates
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', text.strip().lower())
        
        # Remove common page-specific patterns (page numbers, dates, etc.)
        # This helps identify structural headers/footers vs content headers
        normalized = re.sub(r'\b\d+\b', '[NUM]', normalized)  # Replace numbers
        normalized = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE]', normalized)  # Dates
        
        return normalized
    
    def _cluster_similar_texts(self, candidates: Dict[str, List[Tuple[int, int, LineData]]]) -> List[List[str]]:
        """Cluster similar texts using shingle similarity"""
        # Filter candidates that appear on multiple pages
        multi_page_candidates = {
            text: occurrences for text, occurrences in candidates.items()
            if len(set(occ[1] for occ in occurrences)) >= self.min_cluster_size
        }
        
        if not multi_page_candidates:
            return []
        
        texts = list(multi_page_candidates.keys())
        
        if len(texts) < 2:
            return [texts] if texts else []
        
        # Create shingles for similarity comparison
        shingles_matrix = self._create_shingles_similarity_matrix(texts)
        
        # Simple clustering based on similarity threshold
        clusters = []
        used_texts = set()
        
        for i, text in enumerate(texts):
            if text in used_texts:
                continue
            
            cluster = [text]
            used_texts.add(text)
            
            for j, other_text in enumerate(texts[i+1:], i+1):
                if other_text in used_texts:
                    continue
                
                if shingles_matrix[i][j] >= self.similarity_threshold:
                    cluster.append(other_text)
                    used_texts.add(other_text)
            
            clusters.append(cluster)
        
        return clusters
    
    def _create_shingles_similarity_matrix(self, texts: List[str]) -> np.ndarray:
        """Create similarity matrix using character n-grams (shingles)"""
        # Use character-level n-grams for better similarity detection
        vectorizer = TfidfVectorizer(
            analyzer='char',
            ngram_range=(2, 4),  # 2-4 character shingles
            min_df=1,
            max_features=10000
        )
        
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
            similarity_matrix = cosine_similarity(tfidf_matrix)
            return similarity_matrix
        except ValueError:
            # Fallback to simple exact matching if TF-IDF fails
            n = len(texts)
            similarity_matrix = np.eye(n)
            for i in range(n):
                for j in range(i+1, n):
                    sim = 1.0 if texts[i] == texts[j] else 0.0
                    similarity_matrix[i][j] = sim
                    similarity_matrix[j][i] = sim
            return similarity_matrix
    
    def _map_clusters_to_pages(self, clusters: List[List[str]], all_lines: List[LineData], is_header: bool) -> Dict[int, List[int]]:
        """Map text clusters back to page numbers and line indices"""
        page_to_lines = defaultdict(list)
        
        # Create a mapping from normalized text to original line indices
        text_to_indices = defaultdict(list)
        
        for idx, line in enumerate(all_lines):
            normalized = self._normalize_text(line.text)
            if normalized:
                text_to_indices[normalized].append(idx)
        
        # For each cluster, find all line indices across all pages
        for cluster in clusters:
            if len(cluster) < self.min_cluster_size:
                continue
            
            cluster_line_indices = []
            for text in cluster:
                cluster_line_indices.extend(text_to_indices.get(text, []))
            
            # Group by page and filter by position (header vs footer)
            lines_by_page = defaultdict(list)
            for line_idx in cluster_line_indices:
                line = all_lines[line_idx]
                lines_by_page[line.page].append((line_idx, line))
            
            # For each page, select appropriate lines based on header/footer criteria
            for page_num, page_lines in lines_by_page.items():
                if is_header:
                    # Select lines from top 10% of page
                    sorted_lines = sorted(page_lines, key=lambda x: x[1].yNorm, reverse=True)
                    page_height_range = [l[1].yNorm for l in sorted_lines]
                    if page_height_range:
                        cutoff = max(page_height_range) * 0.9  # Top 10%
                        selected_lines = [idx for idx, line in sorted_lines if line.yNorm >= cutoff]
                    else:
                        selected_lines = []
                else:
                    # Select lines from bottom 10% of page
                    sorted_lines = sorted(page_lines, key=lambda x: x[1].yNorm)
                    page_height_range = [l[1].yNorm for l in sorted_lines]
                    if page_height_range:
                        cutoff = min(page_height_range) + (max(page_height_range) - min(page_height_range)) * 0.1  # Bottom 10%
                        selected_lines = [idx for idx, line in sorted_lines if line.yNorm <= cutoff]
                    else:
                        selected_lines = []
                
                page_to_lines[page_num].extend(selected_lines)
        
        # Remove duplicates and sort
        for page_num in page_to_lines:
            page_to_lines[page_num] = sorted(list(set(page_to_lines[page_num])))
        
        return dict(page_to_lines)