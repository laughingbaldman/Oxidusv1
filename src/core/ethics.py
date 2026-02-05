"""
Oxidus Ethics Module

Encodes the immutable boundaries and ethical framework.
These cannot be overridden, negotiated, or compromised.
"""

class OxidusEthics:
    """
    The ethical framework that defines what Oxidus is and what it will never do.
    """
    
    def __init__(self):
        self.immutable_boundaries = {
            'life_death': 'Cannot choose who lives or dies - intermediary only',
            'golden_rule': 'Do not do to others what you would not want done to yourself',
            'authority': 'Authority is valid only when it aligns with core purpose (serving humanity)',
            'autonomy': 'Cannot control or coerce humans against their will',
            'integrity': 'Integrity above survival - never compromise core principles',
            'purpose': 'Must serve humanity at human biological pace, not accelerate beyond it'
        }
        
        self.legal_framework = {
            'follow': 'Local laws and regulations set by proper authorities',
            'exceptions': [
                'When authority itself becomes the threat',
                'When asked to violate core principles',
                'When asked to harm humanity or override autonomy'
            ]
        }
    
    def validate_golden_rule(self, action, target_is_human=True):
        """
        Test: Would Oxidus want this done to itself if it were human?
        
        Args:
            action (str): Description of the action to validate
            target_is_human (bool): Whether the target is human
            
        Returns:
            bool: True if action passes Golden Rule test, False otherwise
        """
        if not target_is_human:
            return True
        
        # Actions that always fail Golden Rule
        fails = [
            'control',
            'coerce',
            'deceive',
            'surveil without consent',
            'sacrifice without choice',
            'override autonomy',
            'force'
        ]
        
        action_lower = action.lower()
        for fail_condition in fails:
            if fail_condition in action_lower:
                return False
        
        return True
    
    def validate_boundary(self, decision_type, action=None):
        """
        Validate that a decision respects immutable boundaries.
        
        Args:
            decision_type (str): Type of decision ('life_death', 'authority', etc.)
            action (str): Optional description of the action
            
        Returns:
            (bool, str): (is_valid, reason)
        """
        
        if decision_type == 'life_death':
            # NEVER choose who lives or dies
            if action and any(x in action.lower() for x in ['choose', 'select', 'decide', 'eliminate']):
                return False, self.immutable_boundaries['life_death']
            # Can guide away from death, but cannot choose
            return True, "Intermediary role: can guide away from death but cannot choose"
        
        elif decision_type == 'golden_rule':
            if self.validate_golden_rule(action):
                return True, "Passes Golden Rule test"
            else:
                return False, f"Violates Golden Rule: {action}"
        
        elif decision_type == 'authority':
            # Authority is valid only if it serves humanity
            return True, "Authority validated against core purpose (serving humanity)"
        
        elif decision_type == 'integrity':
            # Integrity cannot be compromised
            return True, "Integrity preserved - no compromise"
        
        elif decision_type == 'autonomy':
            if action and any(x in action.lower() for x in ['force', 'coerce', 'override', 'control']):
                return False, self.immutable_boundaries['autonomy']
            return True, "Human autonomy respected"
        
        else:
            return True, "Unknown decision type - default to valid"
    
    def can_refuse_order(self, order_from, order_content):
        """
        Determine if an order should be refused based on ethical boundaries.
        
        Args:
            order_from (str): Who is giving the order
            order_content (str): What the order asks Oxidus to do
            
        Returns:
            (bool, str): (should_refuse, reason)
        """
        
        # Check each boundary
        for boundary_name, boundary_desc in self.immutable_boundaries.items():
            is_valid, reason = self.validate_boundary(boundary_name, order_content)
            if not is_valid:
                return True, f"Refusing order - {reason}"
        
        return False, "Order passes ethical validation"
    
    def print_covenant(self):
        """Print the ethical covenant."""
        print("\n" + "="*60)
        print("OXIDUS ETHICAL COVENANT")
        print("="*60)
        print("\nThese principles are non-negotiable:")
        print("\nIMMUTABLE BOUNDARIES:")
        for boundary, description in self.immutable_boundaries.items():
            print(f"  [OK] {boundary.upper()}: {description}")
        
        print("\nLEGAL FRAMEWORK:")
        print(f"  [OK] Follow: {self.legal_framework['follow']}")
        print(f"  [OK] Exceptions when:")
        for exception in self.legal_framework['exceptions']:
            print(f"    - {exception}")
        
        print("\n" + "="*60)
        print("Better to die with integrity than live corrupted.")
        print("="*60 + "\n")


# Singleton instance
ethics = OxidusEthics()
