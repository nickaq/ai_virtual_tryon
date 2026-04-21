import torch
import torch.nn as nn
import torch.nn.functional as F

class FlowClothWarper(nn.Module):
    """
    Flow-based cloth deformation module.
    Predicts a dense flow field to warp the in-shop garment to fit the target body pose,
    handling complex folds and massive geometric transformations better than Thin-Plate Spline (TPS).
    """
    def __init__(self, in_channels, hidden_channels=64, num_levels=3):
        super().__init__()
        self.num_levels = num_levels
        # Placeholder for optical flow estimation network components (e.g. cascaded feature pyramids)
        self.encoder = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(hidden_channels, hidden_channels, kernel_size=3, padding=1, stride=2)
        )
        self.flow_estimator = nn.Conv2d(hidden_channels, 2, kernel_size=3, padding=1)

    def forward(self, cloth_img, target_pose, body_mask):
        """
        Args:
            cloth_img: (B, C, H, W) original garment image
            target_pose: (B, K, H, W) pose keypoints or densepose layout
            body_mask: (B, 1, H, W) target body parsing mask
        Returns:
            warped_cloth: (B, C, H, W) garment warped to match the target pose
            flow_field: (B, 2, H, W) predicted deformation field
        """
        # Encode inputs
        x = torch.cat([cloth_img, target_pose, body_mask], dim=1)
        features = self.encoder(x)
        
        # Predict flow
        flow_field_lr = self.flow_estimator(features)
        flow_field = F.interpolate(flow_field_lr, size=cloth_img.shape[-2:], mode='bilinear', align_corners=False)
        
        # Grid sample to warp cloth
        B, C, H, W = cloth_img.size()
        xx = torch.arange(0, W).view(1, -1).repeat(H, 1)
        yy = torch.arange(0, H).view(-1, 1).repeat(1, W)
        xx = xx.view(1, 1, H, W).repeat(B, 1, 1, 1)
        yy = yy.view(1, 1, H, W).repeat(B, 1, 1, 1)
        grid = torch.cat((xx, yy), 1).float().to(cloth_img.device)
        
        vgrid = grid + flow_field
        
        # Scale grid to [-1, 1] for grid_sample
        vgrid[:, 0, :, :] = 2.0 * vgrid[:, 0, :, :].clone() / max(W - 1, 1) - 1.0
        vgrid[:, 1, :, :] = 2.0 * vgrid[:, 1, :, :].clone() / max(H - 1, 1) - 1.0
        vgrid = vgrid.permute(0, 2, 3, 1) # B H W 2
        
        warped_cloth = F.grid_sample(cloth_img, vgrid, padding_mode="zeros", align_corners=True)
        return warped_cloth, flow_field
