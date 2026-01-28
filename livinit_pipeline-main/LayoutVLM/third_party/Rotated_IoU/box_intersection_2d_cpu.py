"""
Pure PyTorch CPU implementation of 2D oriented box intersection.
No CUDA required.
"""
import torch

EPSILON = 1e-8


def box_intersection_th(corners1: torch.Tensor, corners2: torch.Tensor):
    """Find intersection points of rectangles.

    Args:
        corners1: (B, N, 4, 2)
        corners2: (B, N, 4, 2)

    Returns:
        intersections: (B, N, 4, 4, 2)
        mask: (B, N, 4, 4) bool
    """
    line1 = torch.cat([corners1, corners1[:, :, [1, 2, 3, 0], :]], dim=3)
    line2 = torch.cat([corners2, corners2[:, :, [1, 2, 3, 0], :]], dim=3)

    line1_ext = line1.unsqueeze(3).repeat([1, 1, 1, 4, 1])
    line2_ext = line2.unsqueeze(2).repeat([1, 1, 4, 1, 1])

    x1, y1 = line1_ext[..., 0], line1_ext[..., 1]
    x2, y2 = line1_ext[..., 2], line1_ext[..., 3]
    x3, y3 = line2_ext[..., 0], line2_ext[..., 1]
    x4, y4 = line2_ext[..., 2], line2_ext[..., 3]

    num = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    den_t = (x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)

    t = den_t / (num + EPSILON)
    t = torch.where(num == 0, torch.tensor(-1.0, device=t.device), t)
    mask_t = (t > 0) & (t < 1)

    den_u = (x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)
    u = -den_u / (num + EPSILON)
    u = torch.where(num == 0, torch.tensor(-1.0, device=u.device), u)
    mask_u = (u > 0) & (u < 1)

    mask = mask_t & mask_u
    intersections = torch.stack([x1 + t * (x2 - x1), y1 + t * (y2 - y1)], dim=-1)
    intersections = intersections * mask.float().unsqueeze(-1)

    return intersections, mask


def box1_in_box2(corners1: torch.Tensor, corners2: torch.Tensor):
    """Check if corners of box1 lie in box2.

    Args:
        corners1: (B, N, 4, 2)
        corners2: (B, N, 4, 2)

    Returns:
        c1_in_2: (B, N, 4) Bool
    """
    a = corners2[:, :, 0:1, :]
    b = corners2[:, :, 1:2, :]
    d = corners2[:, :, 3:4, :]

    ab = b - a
    am = corners1 - a
    ad = d - a

    p_ab = torch.sum(ab * am, dim=-1)
    norm_ab = torch.sum(ab * ab, dim=-1)
    p_ad = torch.sum(ad * am, dim=-1)
    norm_ad = torch.sum(ad * ad, dim=-1)

    cond1 = (p_ab / (norm_ab + EPSILON) > -1e-6) & (p_ab / (norm_ab + EPSILON) < 1 + 1e-6)
    cond2 = (p_ad / (norm_ad + EPSILON) > -1e-6) & (p_ad / (norm_ad + EPSILON) < 1 + 1e-6)

    return cond1 & cond2


def box_in_box_th(corners1: torch.Tensor, corners2: torch.Tensor):
    """Check if corners of two boxes lie in each other."""
    c1_in_2 = box1_in_box2(corners1, corners2)
    c2_in_1 = box1_in_box2(corners2, corners1)
    return c1_in_2, c2_in_1


def build_vertices(corners1, corners2, c1_in_2, c2_in_1, inters, mask_inter):
    """Find vertices of intersection area."""
    B, N = corners1.size()[:2]
    vertices = torch.cat([corners1, corners2, inters.view([B, N, -1, 2])], dim=2)
    mask = torch.cat([c1_in_2, c2_in_1, mask_inter.view([B, N, -1])], dim=2)
    return vertices, mask


def sort_indices_cpu(vertices: torch.Tensor, mask: torch.Tensor):
    """Pure PyTorch CPU implementation of vertex sorting by angle.

    Args:
        vertices: (B, N, 24, 2)
        mask: (B, N, 24) bool

    Returns:
        sorted_index: (B, N, 9)
    """
    B, N, num_vertices = vertices.shape[:3]
    device = vertices.device

    # Compute centroid of valid vertices
    num_valid = torch.sum(mask.int(), dim=2, keepdim=True).float()
    num_valid = torch.clamp(num_valid, min=1)  # avoid division by zero
    mean = torch.sum(vertices * mask.float().unsqueeze(-1), dim=2, keepdim=True) / num_valid.unsqueeze(-1)

    # Normalize vertices relative to centroid
    vertices_centered = vertices - mean

    # Compute angles
    angles = torch.atan2(vertices_centered[..., 1], vertices_centered[..., 0])

    # Set angles of invalid vertices to large value so they sort to end
    angles = torch.where(mask, angles, torch.tensor(1e10, device=device))

    # Sort by angle
    sorted_indices = torch.argsort(angles, dim=2)

    # Build output indices (first 9, with wrap-around for closed polygon)
    result = torch.zeros(B, N, 9, dtype=torch.long, device=device)

    for b in range(B):
        for n in range(N):
            nv = int(mask[b, n].sum().item())
            if nv == 0:
                # No valid vertices - use arbitrary indices (will be masked anyway)
                result[b, n, :] = 8  # index of a zero-valued intersection point
                continue

            valid_sorted = sorted_indices[b, n, :nv]

            # Fill result: valid vertices + wrap to first + padding
            for i in range(min(nv, 8)):
                result[b, n, i] = valid_sorted[i]

            # Wrap around to close polygon
            if nv > 0:
                result[b, n, min(nv, 8)] = valid_sorted[0]

            # Pad remaining with last valid intersection index
            for i in range(min(nv + 1, 9), 9):
                result[b, n, i] = 8

    return result


def sort_indices_cpu_vectorized(vertices: torch.Tensor, mask: torch.Tensor):
    """Vectorized CPU implementation of vertex sorting by angle.

    Args:
        vertices: (B, N, 24, 2)
        mask: (B, N, 24) bool

    Returns:
        sorted_index: (B, N, 9)
    """
    B, N, num_vertices = vertices.shape[:3]
    device = vertices.device

    # Compute centroid
    num_valid = torch.sum(mask.float(), dim=2, keepdim=True).clamp(min=1)
    mean = torch.sum(vertices * mask.float().unsqueeze(-1), dim=2, keepdim=True) / num_valid.unsqueeze(-1)
    vertices_centered = vertices - mean

    # Compute angles
    angles = torch.atan2(vertices_centered[..., 1], vertices_centered[..., 0])
    angles = torch.where(mask, angles, torch.tensor(1e10, device=device, dtype=angles.dtype))

    # Sort by angle
    sorted_indices = torch.argsort(angles, dim=2)

    # Take first 9 indices (8 max polygon vertices + 1 for closure)
    result = sorted_indices[:, :, :9].clone()

    # For the 9th position, copy the first valid vertex to close the polygon
    # This is an approximation - the exact CUDA implementation is more nuanced
    num_valid_int = num_valid.squeeze(-1).long().clamp(max=8)

    # Set last position to first sorted index to close polygon
    result[:, :, 8] = sorted_indices[:, :, 0]

    # For positions beyond num_valid, set to an arbitrary valid index
    for i in range(8):
        too_far = (i >= num_valid_int)
        result[:, :, i] = torch.where(too_far.squeeze(-1), sorted_indices[:, :, 0], result[:, :, i])

    return result


def calculate_area(idx_sorted: torch.Tensor, vertices: torch.Tensor):
    """Calculate area of intersection.

    Args:
        idx_sorted: (B, N, 9)
        vertices: (B, N, 24, 2)

    Returns:
        area: (B, N)
        selected: (B, N, 9, 2)
    """
    idx_ext = idx_sorted.unsqueeze(-1).repeat([1, 1, 1, 2])
    selected = torch.gather(vertices, 2, idx_ext)

    # Shoelace formula
    total = selected[:, :, 0:-1, 0] * selected[:, :, 1:, 1] - selected[:, :, 0:-1, 1] * selected[:, :, 1:, 0]
    total = torch.sum(total, dim=2)
    area = torch.abs(total) / 2

    return area, selected


def oriented_box_intersection_2d(corners1: torch.Tensor, corners2: torch.Tensor):
    """Calculate intersection area of 2D rectangles.

    Args:
        corners1: (B, N, 4, 2)
        corners2: (B, N, 4, 2)

    Returns:
        area: (B, N)
        selected: (B, N, 9, 2)
    """
    inters, mask_inter = box_intersection_th(corners1, corners2)
    c12, c21 = box_in_box_th(corners1, corners2)
    vertices, mask = build_vertices(corners1, corners2, c12, c21, inters, mask_inter)
    sorted_indices = sort_indices_cpu_vectorized(vertices, mask)
    return calculate_area(sorted_indices, vertices)
