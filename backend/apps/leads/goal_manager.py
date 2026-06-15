"""
Goal Manager Service for AI Agent.

Manages conversation goals for leads:
- Creates initial goals based on lead state
- Tracks goal progress
- Marks goals as completed
- Generates new goals as needed
"""
import logging
from typing import Optional
from django.utils import timezone
from .models import Lead, LeadGoal, LeadActivity

logger = logging.getLogger(__name__)


class GoalManager:
    """Manages conversation goals for leads."""

    # Default goals based on missing lead data
    DATA_COLLECTION_GOALS = {
        'email': 'collect_email',
        'phone': 'collect_phone',
    }

    # Stage-based goals
    STAGE_GOALS = {
        'new': ['qualify_lead'],
        'contacted': ['qualify_lead', 'schedule_call'],
        'qualified': ['send_info', 'schedule_meeting'],
        'proposal': ['send_proposal', 'handle_objection'],
        'negotiation': ['close_deal', 'handle_objection'],
    }

    # Goal priorities by type
    GOAL_PRIORITIES = {
        'close_deal': LeadGoal.PRIORITY_HIGH,
        'handle_objection': LeadGoal.PRIORITY_HIGH,
        'schedule_meeting': LeadGoal.PRIORITY_HIGH,
        'schedule_call': LeadGoal.PRIORITY_MEDIUM,
        'send_proposal': LeadGoal.PRIORITY_MEDIUM,
        'qualify_lead': LeadGoal.PRIORITY_MEDIUM,
        'send_info': LeadGoal.PRIORITY_MEDIUM,
        'collect_email': LeadGoal.PRIORITY_LOW,
        'collect_phone': LeadGoal.PRIORITY_LOW,
        'get_decision_maker': LeadGoal.PRIORITY_LOW,
    }

    def get_active_goals(self, lead: Lead) -> list:
        """Get all active goals for a lead."""
        return list(lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).order_by('-priority', '-created_at'))

    def create_initial_goals(self, lead: Lead) -> list:
        """
        Create initial goals for a lead based on missing data and stage.

        Returns list of created goals.
        """
        created_goals = []
        existing_goal_types = set(
            lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).values_list('goal_type', flat=True)
        )

        # Data collection goals
        if not lead.email and 'collect_email' not in existing_goal_types:
            goal = self._create_goal(lead, 'collect_email', "Collect lead's email address")
            if goal:
                created_goals.append(goal)

        if not lead.phone and 'collect_phone' not in existing_goal_types:
            goal = self._create_goal(lead, 'collect_phone', "Collect lead's phone number")
            if goal:
                created_goals.append(goal)

        # Stage-based goals
        stage_goals = self.STAGE_GOALS.get(lead.status, [])
        for goal_type in stage_goals:
            if goal_type not in existing_goal_types:
                goal = self._create_goal(lead, goal_type)
                if goal:
                    created_goals.append(goal)

        return created_goals

    def _create_goal(self, lead: Lead, goal_type: str, description: str = '') -> Optional[LeadGoal]:
        """Create a single goal for a lead."""
        try:
            priority = self.GOAL_PRIORITIES.get(goal_type, LeadGoal.PRIORITY_MEDIUM)

            goal = LeadGoal.objects.create(
                lead=lead,
                goal_type=goal_type,
                priority=priority,
                description=description,
                is_ai_generated=True,
            )

            # Log activity
            LeadActivity.objects.create(
                lead=lead,
                activity_type=LeadActivity.TYPE_GOAL_CREATED,
                description=f"AI created goal: {goal.get_goal_type_display()}",
                metadata={
                    'goal_id': goal.id,
                    'goal_type': goal_type,
                    'priority': priority,
                    'is_ai_generated': True,
                }
            )

            logger.info(f"Created goal '{goal_type}' for lead {lead.id}")
            return goal

        except Exception as e:
            logger.error(f"Error creating goal for lead {lead.id}: {e}")
            return None

    def complete_goal(self, lead: Lead, goal_type: str, achieved_value: str = '') -> bool:
        """
        Mark a goal as completed.

        Returns True if a goal was completed, False otherwise.
        """
        goal = lead.goals.filter(
            goal_type=goal_type,
            status=LeadGoal.STATUS_ACTIVE
        ).first()

        if not goal:
            return False

        goal.status = LeadGoal.STATUS_COMPLETED
        goal.completed_at = timezone.now()
        goal.achieved_value = achieved_value
        goal.save()

        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_GOAL_COMPLETED,
            description=f"Goal achieved: {goal.get_goal_type_display()}",
            metadata={
                'goal_id': goal.id,
                'goal_type': goal_type,
                'achieved_value': achieved_value,
            }
        )

        logger.info(f"Completed goal '{goal_type}' for lead {lead.id}")
        return True

    def complete_goals_by_types(self, lead: Lead, goal_types: list, analysis_data: dict = None) -> list:
        """
        Complete multiple goals based on conversation analysis.

        Returns list of goal_type strings that were actually completed.
        """
        completed_types = []

        for goal_type in goal_types:
            achieved_value = ''

            # Extract achieved value from analysis data
            if analysis_data:
                if goal_type == 'collect_email' and analysis_data.get('extracted_email'):
                    achieved_value = analysis_data['extracted_email']
                elif goal_type == 'collect_phone' and analysis_data.get('extracted_phone'):
                    achieved_value = analysis_data['extracted_phone']

            if self.complete_goal(lead, goal_type, achieved_value):
                completed_types.append(goal_type)

        return completed_types

    def increment_goal_attempt(self, lead: Lead, goal_type: str) -> None:
        """Increment the attempt counter for a goal."""
        goal = lead.goals.filter(
            goal_type=goal_type,
            status=LeadGoal.STATUS_ACTIVE
        ).first()

        if goal:
            goal.attempts += 1
            goal.save(update_fields=['attempts'])

    def abandon_goal(self, lead: Lead, goal_type: str, reason: str = '') -> bool:
        """Mark a goal as abandoned (no longer pursuing)."""
        goal = lead.goals.filter(
            goal_type=goal_type,
            status=LeadGoal.STATUS_ACTIVE
        ).first()

        if not goal:
            return False

        goal.status = LeadGoal.STATUS_ABANDONED
        goal.save(update_fields=['status'])

        logger.info(f"Abandoned goal '{goal_type}' for lead {lead.id}: {reason}")
        return True

    def update_goals_for_stage_change(self, lead: Lead, new_stage: str) -> list:
        """
        Update goals when a lead moves to a new stage.

        - Abandons irrelevant goals
        - Creates new stage-appropriate goals

        Returns list of newly created goals.
        """
        # Mark some goals as completed if stage advanced
        if new_stage in ['qualified', 'proposal', 'negotiation', 'converted']:
            self.complete_goal(lead, 'qualify_lead', f"Lead moved to {new_stage}")

        if new_stage in ['proposal', 'negotiation', 'converted']:
            self.complete_goal(lead, 'schedule_call', f"Lead moved to {new_stage}")
            self.complete_goal(lead, 'schedule_meeting', f"Lead moved to {new_stage}")

        if new_stage in ['negotiation', 'converted']:
            self.complete_goal(lead, 'send_proposal', f"Lead moved to {new_stage}")

        if new_stage == 'converted':
            self.complete_goal(lead, 'close_deal', "Deal closed")
            # Mark all remaining active goals as completed
            lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).update(
                status=LeadGoal.STATUS_COMPLETED,
                completed_at=timezone.now()
            )
            return []

        # Create new goals for the stage
        return self.create_initial_goals(lead)

    def get_goals_context_for_ai(self, lead: Lead) -> str:
        """
        Get a string representation of active goals for AI prompt context.
        """
        active_goals = self.get_active_goals(lead)

        if not active_goals:
            return "No specific goals set for this lead."

        lines = ["Current goals to work toward:"]
        for goal in active_goals:
            priority_label = {
                LeadGoal.PRIORITY_HIGH: "HIGH",
                LeadGoal.PRIORITY_MEDIUM: "MEDIUM",
                LeadGoal.PRIORITY_LOW: "LOW",
            }.get(goal.priority, "MEDIUM")

            lines.append(f"- [{priority_label}] {goal.get_goal_type_display()}")
            if goal.description:
                lines.append(f"  Context: {goal.description}")
            if goal.attempts > 0:
                lines.append(f"  Attempts: {goal.attempts}")

        return "\n".join(lines)

    def suggest_goals_from_analysis(self, lead: Lead, analysis: dict) -> list:
        """
        Create new goals based on AI conversation analysis.

        Returns list of created goals.
        """
        suggested = analysis.get('new_goals_suggested', [])
        if not suggested:
            return []

        created_goals = []
        existing_goal_types = set(
            lead.goals.filter(status=LeadGoal.STATUS_ACTIVE).values_list('goal_type', flat=True)
        )

        for goal_type in suggested:
            if goal_type not in existing_goal_types:
                # Validate goal type
                valid_types = [choice[0] for choice in LeadGoal.GOAL_TYPES]
                if goal_type in valid_types:
                    goal = self._create_goal(lead, goal_type, "AI suggested based on conversation")
                    if goal:
                        created_goals.append(goal)

        return created_goals


# Singleton instance
goal_manager = GoalManager()
