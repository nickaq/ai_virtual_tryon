import torch
import torch.nn as nn

class OcclusionAwareMasker(nn.Module):
    """
    Explicitly models occlusions where body parts (like hair or crossed arms) 
    might overlap the garment. Uses depth/normal cues if available to predict visibility.
    """
    def __init__(self, in_channels, hidden_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_channels, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_dim, hidden_dim, kernel_size=3, padding=1),
            nn.BatchNorm2d(hidden_dim),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_dim, 1, kernel_size=1),
            nn.Sigmoid()
        )

    def forward(self, parsed_body, depth_map, warped_cloth):
        """
        Args:
            parsed_body: (B, C1, H, W) Body segmentation regions
            depth_map: (B, 1, H, W) Depth cue (if available)
            warped_cloth: (B, 3, H, W) The flow-warped garment
        Returns:
            visibility_mask: (B, 1, H, W) Continuous mask indicating occlusion (0 = occluded, 1 = visible)
        """
        x = torch.cat([parsed_body, depth_map, warped_cloth], dim=1)
        visibility_mask = self.net(x)
        return visibility_mask
