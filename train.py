import torch
import torch.optim as optim
import torch.nn as nn
import os
from models.unetgenerator import UNetGenerator
from models.patchgandiscriminator import PatchGANDiscriminator
from datasets.dataloader import create_dataloaders

# Set up device: use GPU if available, otherwise CPU
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")

# Load Data
sketch_dir = "gamma_inverted_sketches"  # or "sketches"
photo_dir = "portraits"
train_loader, val_loader, test_loader = create_dataloaders(sketch_dir, photo_dir, batch_size=16)

# Initialize models
generator = UNetGenerator().to(device)
discriminator = PatchGANDiscriminator().to(device)

# Define loss functions
criterion_GAN = nn.BCEWithLogitsLoss()  # Adversarial loss
criterion_L1 = nn.L1Loss()  # L1 loss for pixel-level similarity

# Optimizers
optimizer_G = optim.Adam(generator.parameters(), lr=0.0002, betas=(0.5, 0.999))
optimizer_D = optim.Adam(discriminator.parameters(), lr=0.0002, betas=(0.5, 0.999))

# Training loop settings
num_epochs = 50  # Adjust as needed
best_val_loss = float("inf")
patience = 10  # Early stopping if no improvement after X epochs
trigger_times = 0

if not os.path.exists("saved_models"):
    os.makedirs("saved_models")



# Start training
for epoch in range(num_epochs):
    generator.train()
    discriminator.train()
    
    for i, (sketch, real_image) in enumerate(train_loader):
        sketch = sketch.to(device)
        real_image = real_image.to(device)

        # === Train Discriminator ===
        optimizer_D.zero_grad()
        
        # Real images
        real_output = discriminator(real_image, sketch)
        real_labels = torch.ones_like(real_output).to(device)
        loss_real = criterion_GAN(real_output, real_labels)

        # Fake images (generated by generator)
        fake_image = generator(sketch)
        fake_output = discriminator(fake_image.detach(), sketch)
        fake_labels = torch.zeros_like(fake_output).to(device)
        loss_fake = criterion_GAN(fake_output, fake_labels)

        loss_D = (loss_real + loss_fake) * 0.5
        loss_D.backward()
        optimizer_D.step()

        # === Train Generator ===
        optimizer_G.zero_grad()

        # GAN loss
        fake_output = discriminator(fake_image, sketch)
        loss_G_GAN = criterion_GAN(fake_output, real_labels)

        # L1 loss (pixel-level similarity)
        loss_G_L1 = criterion_L1(fake_image, real_image) * 100  # Scale L1 loss by 100

        loss_G = loss_G_GAN + loss_G_L1
        loss_G.backward()
        optimizer_G.step()

        print(f"[Epoch {epoch}/{num_epochs}] [Batch {i}/{len(train_loader)}] [D loss: {loss_D.item():.4f}] [G loss: {loss_G.item():.4f}]")

    # Validation Phase
    generator.eval()
    val_loss = 0.0
    with torch.no_grad():
        for val_sketch, val_real_image in val_loader:
            val_sketch = val_sketch.to(device)
            val_real_image = val_real_image.to(device)

            val_fake_image = generator(val_sketch)
            val_loss += criterion_L1(val_fake_image, val_real_image).item()

    val_loss /= len(val_loader)
    print(f"Validation Loss: {val_loss:.4f}")

    # Early stopping
    if val_loss < best_val_loss:
        best_val_loss = val_loss
        trigger_times = 0

        # Save best models
        torch.save(generator.state_dict(), "saved_models/best_generator.pth")
        torch.save(discriminator.state_dict(), "saved_models/best_discriminator.pth")
        print(f"Model saved at epoch {epoch} with validation loss: {val_loss:.4f}")
    else:
        trigger_times += 1
        if trigger_times >= patience:
            print(f"Early stopping triggered at epoch {epoch}")
            break