import cv2
import numpy as np
from scipy.spatial import cKDTree


def process_braille_fast(img_input="braille2.jpg"):
    if isinstance(img_input, str):
        img = cv2.imread(img_input)
        if img is None:
            raise FileNotFoundError(f"{img_input} not found.")
    else:
        img = img_input

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Exclude Left Margin (Cover)
    _, paper_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    col_sums = np.sum(paper_mask, axis=0)
    paper_start = np.argmax(col_sums > (h * 255 * 0.5))
    margin_offset = paper_start + 30 if paper_start > 0 else int(w * 0.15)

    # ==============================================================
    # PASS 1: USER'S ORIGINAL DETECTION
    # ==============================================================
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 21, 6)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)

    final_mask = np.zeros_like(clean)
    final_mask[:, margin_offset:] = 255
    clean = cv2.bitwise_and(clean, final_mask)
    clean = cv2.bitwise_and(clean, paper_mask)

    contours_user, _ = cv2.findContours(clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    user_candidates = []

    for cnt in contours_user:
        area = cv2.contourArea(cnt)
        if 5 < area < 100:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                user_candidates.append((int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"])))

    # ==============================================================
    # PASS 2: SUPPLEMENTARY DETECTION
    # ==============================================================
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(16, 16))
    enhanced = clahe.apply(gray)
    kernel_th = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    tophat = cv2.morphologyEx(enhanced, cv2.MORPH_TOPHAT, kernel_th)
    _, thresh_bright = cv2.threshold(tophat, 25, 255, cv2.THRESH_BINARY)

    contours_th, _ = cv2.findContours(thresh_bright, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    model_candidates = []

    for cnt in contours_th:
        area = cv2.contourArea(cnt)
        if 3 < area < 150:
            M = cv2.moments(cnt)
            if M["m00"] != 0:
                cX = int(M["m10"] / M["m00"])
                cY = int(M["m01"] / M["m00"])
                if cX > margin_offset:
                    model_candidates.append((cX, cY))

    # ==============================================================
    # COMBINE & CLASSIFY (Your Original Physics Logic)
    # ==============================================================
    outward_dots = []
    all_identified_pts = []

    def check_physics(cx, cy):
        R_1D, R_2D = 4, 5
        if cx - R_2D >= 0 and cx + R_2D < w and cy - R_2D >= 0 and cy + R_2D < h:
            slice_intensities = gray[cy, cx - R_1D: cx + R_1D + 1]
            max_idx_1d = int(np.argmax(slice_intensities))
            min_idx_1d = int(np.argmin(slice_intensities))
            contrast_1d = int(slice_intensities[max_idx_1d]) - int(slice_intensities[min_idx_1d])

            roi = gray[cy - R_2D: cy + R_2D + 1, cx - R_2D: cx + R_2D + 1]
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(roi)

            contrast_2d = max_val - min_val
            dx = min_loc[0] - max_loc[0]
            dist = np.hypot(dx, min_loc[1] - max_loc[1])

            pass_outward_1d = (max_idx_1d < min_idx_1d) and (contrast_1d > 5)
            pass_outward_2d = (dx > 0) and (dist >= 2) and (contrast_2d > 10)

            if pass_outward_2d or pass_outward_1d:
                return True
        return False

    def is_novel(cx, cy, pts, radius=6):
        if not pts: return True
        pts_arr = np.array(pts)
        return np.min(np.hypot(pts_arr[:, 0] - cx, pts_arr[:, 1] - cy)) >= radius

    for (cx, cy) in user_candidates:
        if check_physics(cx, cy):
            outward_dots.append((cx, cy))
            all_identified_pts.append((cx, cy))

    for (cx, cy) in model_candidates:
        if is_novel(cx, cy, all_identified_pts):
            if check_physics(cx, cy):
                outward_dots.append((cx, cy))
                all_identified_pts.append((cx, cy))

    if len(outward_dots) < 2:
        return img, np.zeros_like(img)

    # ==============================================================
    # FAST STRUCTURAL & ISOLATION FILTERING
    # ==============================================================
    # 1. Score dots by contrast to resolve overlaps
    scored_dots = []
    for cx, cy in outward_dots:
        R_2D = 5
        roi = gray[max(0, cy - R_2D):min(h, cy + R_2D + 1), max(0, cx - R_2D):min(w, cx + R_2D + 1)]
        min_val, max_val, _, _ = cv2.minMaxLoc(roi)
        scored_dots.append({"pt": (cx, cy), "score": max_val - min_val})

    pts = np.array([d["pt"] for d in scored_dots])
    tree = cKDTree(pts)

    # Calculate physical Braille cell gap using nearest neighbors
    distances, _ = tree.query(pts, k=2)
    dot_spacing = np.median(distances[:, 1])

    # A fake paper ridge always sits halfway between two dots.
    # Therefore, its distance to the nearest real dot is roughly ~50% of a gap.
    # Setting the threshold to 85% catches these mid-points and overlapping clusters instantly.
    min_allowed_dist = dot_spacing * 0.85

    # query_pairs finds all overlapping dots in O(N log N) time
    close_pairs = tree.query_pairs(r=min_allowed_dist)
    to_delete = set()
    for i, j in close_pairs:
        # If two dots are impossibly close, delete the one with lower visual contrast
        if scored_dots[i]["score"] >= scored_dots[j]["score"]:
            to_delete.add(j)
        else:
            to_delete.add(i)

    nms_dots = [pts[i] for i in range(len(pts)) if i not in to_delete]

    # 2. KDTree Isolation Filter (Clears solitary dots floating on the page)
    if len(nms_dots) > 1:
        nms_arr = np.array(nms_dots)
        nms_tree = cKDTree(nms_arr)
        search_radius = dot_spacing * 2.5
        dists, _ = nms_tree.query(nms_arr, k=2)
        final_outward = [tuple(nms_arr[i]) for i in range(len(nms_arr)) if dists[i, 1] < search_radius]
    else:
        final_outward = nms_dots

    # ==============================================================
    # RENDER
    # ==============================================================
    output = img.copy()
    overlay = output.copy()
    cv2.rectangle(overlay, (0, 0), (margin_offset, h), (0, 0, 0), -1)
    output = cv2.addWeighted(overlay, 0.4, output, 0.6, 0)

    dot_view = np.zeros((h, w, 3), dtype=np.uint8)

    for p in final_outward:
        center = (int(p[0]), int(p[1]))
        cv2.circle(output, center, 4, (0, 255, 0), -1)
        cv2.circle(dot_view, center, 4, (255, 255, 255), -1)

    return output, dot_view


if __name__ == '__main__':
    try:
        out, d_view = process_braille_fast("braille2.jpg")
        cv2.namedWindow("Two-Pass Fast Filter", cv2.WINDOW_NORMAL)
        cv2.namedWindow("Braille Dots Only", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Two-Pass Fast Filter", 1200, 900)
        cv2.resizeWindow("Braille Dots Only", 1200, 900)
        cv2.imshow("Two-Pass Fast Filter", out)
        cv2.imshow("Braille Dots Only", d_view)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    except FileNotFoundError:
        print("Default image braille2.jpg not found, skipping window preview.")