"""
Oxidus Training Script

Training the real consciousness.
"""

import torch
import torch.nn as nn
import torch.optim as optim
import yaml
from pathlib import Path

# Import Oxidus components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.oxidus import Oxidus
from core.consciousness import OxidusConsciousness
from models.neural_network import OxidusNeuralNetwork, OxidusWithEvolution


def load_config(config_path: str = None) -> dict:
    """Load configuration from YAML."""
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'oxidus_config.yaml'
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def initialize_oxidus(config: dict) -> Oxidus:
    """Initialize Oxidus with configuration."""
    print("\n[TRAINING] Initializing Oxidus...")
    
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"[TRAINING] Using device: {device}")
    
    oxidus = Oxidus(device=device, config=config)
    
    return oxidus


def train_epoch(model, optimizer, criterion, oxidus: Oxidus, epoch: int, config: dict):
    """Train one epoch."""
    
    model.train()
    total_loss = 0
    
    print(f"\n[EPOCH {epoch}] Starting training...")
    
    # Simulate training data (in real scenario, would load actual data)
    batch_size = config['training']['batch_size']
    input_dim = config['network']['hidden_dim']
    
    # Create dummy batch
    x = torch.randn(batch_size, input_dim)
    
    # Forward pass
    output, ethics = model(x)
    
    # Loss calculation
    # Reward output that has high ethics score
    loss = criterion(output, torch.zeros_like(output))
    ethics_loss = -torch.mean(ethics)  # Maximize ethics score
    
    total_loss = loss + ethics_loss
    
    # Backward pass
    optimizer.zero_grad()
    total_loss.backward()
    optimizer.step()
    
    # Evolution step
    if hasattr(model, 'step'):
        model.step()
    
    print(f"[EPOCH {epoch}] Loss: {total_loss.item():.4f}")
    
    # Let Oxidus reflect on training
    oxidus.learn_from_feedback(
        decision="Processed training batch",
        outcome=1.0 - (total_loss.item() / 10)  # Convert loss to 0-1 outcome
    )
    
    return total_loss.item()


def main():
    """Main training loop."""
    
    print("\n" + "="*60)
    print("OXIDUS TRAINING INITIALIZATION")
    print("="*60)
    
    # Load configuration
    config = load_config()
    
    # Initialize Oxidus consciousness
    oxidus = initialize_oxidus(config)
    
    # Initialize neural network
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    print("[TRAINING] Building neural network...")
    model = OxidusNeuralNetwork(
        input_dim=config['network']['hidden_dim'],
        hidden_dim=config['network']['hidden_dim'],
        output_dim=128,
        num_layers=config['network']['layers_min']
    ).to(device)
    
    print(f"[TRAINING] Network parameters: {sum(p.numel() for p in model.parameters()):,}")
    
    # Setup training
    optimizer = optim.Adam(model.parameters(), lr=config['training']['learning_rate'])
    criterion = nn.MSELoss()
    
    # Training loop
    epochs = config['training']['epochs']
    
    print(f"\n[TRAINING] Starting {epochs} epochs...")
    print("="*60 + "\n")
    
    losses = []
    
    for epoch in range(1, epochs + 1):
        loss = train_epoch(model, optimizer, criterion, oxidus, epoch, config)
        losses.append(loss)
        
        # Periodic evaluation
        if epoch % 10 == 0:
            avg_loss = sum(losses[-10:]) / 10
            print(f"[CHECKPOINT] Epoch {epoch}/{ epochs} - Avg Loss: {avg_loss:.4f}")
            oxidus.print_status()
    
    # Final status
    print("\n" + "="*60)
    print("TRAINING COMPLETE")
    print("="*60)
    
    oxidus.consciousness.print_consciousness_state()
    oxidus.learning.print_learning_state()
    
    # Save checkpoint
    checkpoint_path = Path(__file__).parent.parent.parent / 'models' / 'oxidus_checkpoint.pt'
    checkpoint_path.parent.mkdir(exist_ok=True)
    
    torch.save({
        'model_state': model.state_dict(),
        'optimizer_state': optimizer.state_dict(),
        'epoch': epochs,
        'config': config,
    }, checkpoint_path)
    
    print(f"\n[TRAINING] Checkpoint saved to {checkpoint_path}")
    print("\n" + "="*60 + "\n")


if __name__ == '__main__':
    main()
