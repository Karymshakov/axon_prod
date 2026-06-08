"""
Task Executor Service for AI Agent.

Executes auto-executable tasks autonomously:
- Send messages
- Send documents/info
- Schedule follow-ups
"""
import json
import logging
import asyncio
from typing import Optional
from django.utils import timezone
from .models import Lead, Task, LeadActivity, AIConfig
from .telegram_service import telegram_service
from .instagram_service import instagram_service
from .whatsapp_service import whatsapp_service
from .ai_service import ai_service
from .channel_ai_control import is_channel_ai_globally_paused

logger = logging.getLogger(__name__)


class TaskExecutor:
    """Executes auto-executable tasks for the AI agent."""

    def get_pending_auto_tasks(self, lead: Lead = None) -> list:
        """Get all pending auto-executable tasks, optionally filtered by lead."""
        queryset = Task.objects.filter(
            is_auto_executable=True,
            status=Task.STATUS_PENDING,
            due_date__lte=timezone.now().date()
        )

        if lead:
            queryset = queryset.filter(lead=lead)

        return list(queryset.select_related('lead'))

    def execute_task(self, task: Task) -> bool:
        """
        Execute a single auto-executable task.

        Returns True if execution was successful.
        """
        if not task.is_auto_executable:
            logger.warning(f"Task {task.id} is not auto-executable")
            return False

        if task.status != Task.STATUS_PENDING:
            logger.warning(f"Task {task.id} is not pending (status: {task.status})")
            return False

        # Mark as in progress
        task.status = Task.STATUS_IN_PROGRESS
        task.save(update_fields=['status'])

        try:
            success = False
            result = ""

            if task.execution_type == 'send_message':
                success, result = self._execute_send_message(task)
            elif task.execution_type == 'send_document':
                success, result = self._execute_send_document(task)
            elif task.execution_type == 'schedule_followup':
                success, result = self._execute_schedule_followup(task)
            else:
                # For manual tasks or unknown types, just mark complete
                success = True
                result = "Task marked as complete (manual execution assumed)"

            if success:
                task.status = Task.STATUS_COMPLETED
                task.completed_at = timezone.now()
                task.executed_at = timezone.now()
                task.execution_result = result
                task.save()

                # Log activity
                LeadActivity.objects.create(
                    lead=task.lead,
                    activity_type=LeadActivity.TYPE_TASK_AUTO_COMPLETED,
                    description=f"AI completed task: {task.title}",
                    metadata={
                        'task_id': task.id,
                        'task_title': task.title,
                        'execution_type': task.execution_type,
                        'result': result[:500] if result else '',
                        'is_ai_action': True,
                    }
                )

                logger.info(f"AI executed task {task.id}: {task.title}")
                return True
            else:
                # Execution failed, revert to pending
                task.status = Task.STATUS_PENDING
                task.execution_result = f"Failed: {result}"
                task.save(update_fields=['status', 'execution_result'])
                logger.error(f"Failed to execute task {task.id}: {result}")
                return False

        except Exception as e:
            task.status = Task.STATUS_PENDING
            task.execution_result = f"Error: {str(e)}"
            task.save(update_fields=['status', 'execution_result'])
            logger.error(f"Error executing task {task.id}: {e}", exc_info=True)
            return False

    def _execute_send_message(self, task: Task) -> tuple[bool, str]:
        """
        Execute a send_message task.

        Uses the execution_content as the message, or generates one.
        """
        lead = task.lead
        message = task.execution_content

        # Generate message if not provided
        if not message:
            message = self._generate_task_message(task)

        if not message:
            return False, "No message content to send"

        # Determine channel and send
        channel, success = self._send_to_lead(lead, message)

        if success:
            return True, f"Message sent via {channel}"
        else:
            return False, f"Failed to send message via any channel"

    def _execute_send_document(self, task: Task) -> tuple[bool, str]:
        """Execute a send_document task."""
        lead = task.lead

        message = self._generate_task_message(task)

        if not message:
            return False, "No content to send"

        channel, success = self._send_to_lead(lead, message)

        if success:
            return True, f"Document/info sent via {channel}"
        else:
            return False, "Failed to send document"

    def _execute_schedule_followup(self, task: Task) -> tuple[bool, str]:
        """
        Execute a schedule_followup task.

        Creates a new follow-up task for later.
        """
        from datetime import timedelta

        lead = task.lead

        # Create a new follow-up task for 2 days from now
        new_task = Task.objects.create(
            lead=lead,
            title=f"Follow up: {task.title}",
            description=f"Scheduled follow-up from completed task: {task.description}",
            task_type='follow_up',
            due_date=timezone.now().date() + timedelta(days=2),
            is_auto_executable=True,
            execution_type='send_message',
            is_ai_generated=True,
        )

        return True, f"Follow-up task created (ID: {new_task.id})"

    def _generate_task_message(self, task: Task) -> Optional[str]:
        """Generate a message for a task using AI."""
        lead = task.lead
        config = AIConfig.get_config()

        prompt = f"""Generate a brief, professional message for this sales task.

TASK: {task.title}
DESCRIPTION: {task.description}
TASK TYPE: {task.task_type}

LEAD INFO:
- Contact: {lead.contact_person or 'Unknown'}
- Current Stage: {lead.status}

COMPANY CONTEXT:
{config.company_profile[:500] if config.company_profile else 'No company profile available'}

Generate a concise, friendly message (max 500 characters) that accomplishes this task.
Be professional but warm. Include a clear call to action if appropriate.
Respond with ONLY the message text, nothing else."""

        try:
            response = ai_service.generate_response_with_messages([
                {"role": "system", "content": "You are a helpful sales assistant. Write concise, professional messages."},
                {"role": "user", "content": prompt}
            ])
            return response.strip() if response else None
        except Exception as e:
            logger.error(f"Error generating task message: {e}")
            return None

    def _send_to_lead(self, lead: Lead, message: str) -> tuple[str, bool]:
        """
        Send a message to a lead via their preferred/available channel.

        Returns (channel_name, success).
        """
        # Try channels in order of preference
        channels = []

        if lead.telegram_chat_id:
            channels.append(('telegram', lead.telegram_chat_id))
        if lead.instagram_user_id:
            channels.append(('instagram', lead.instagram_user_id))
        if lead.whatsapp_phone:
            channels.append(('whatsapp', lead.whatsapp_phone))

        for channel_name, identifier in channels:
            try:
                if is_channel_ai_globally_paused(channel_name, lead=lead):
                    continue
                success = False

                if channel_name == 'telegram':
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        telegram_service.send_message(identifier, message)
                    )
                    loop.close()
                    success = result is not None

                    if success:
                        LeadActivity.objects.create(
                            lead=lead,
                            activity_type=LeadActivity.TYPE_TELEGRAM_SENT,
                            description="AI sent message via Telegram",
                            metadata={'text': message[:500], 'is_ai_action': True}
                        )

                elif channel_name == 'instagram':
                    result = instagram_service.send_message(identifier, message)
                    success = result is not None

                    if success:
                        LeadActivity.objects.create(
                            lead=lead,
                            activity_type=LeadActivity.TYPE_INSTAGRAM_SENT,
                            description="AI sent message via Instagram",
                            echo_origin=LeadActivity.ECHO_ORIGIN_CRM,
                            metadata={
                                'message_id': result.get('message_id') if result else None,
                                'text': message[:500],
                                'is_ai_action': True,
                                'echo_origin': LeadActivity.ECHO_ORIGIN_CRM,
                            }
                        )

                elif channel_name == 'whatsapp':
                    result = whatsapp_service.send_message(identifier, message, org=lead.organization)
                    success = result is not None

                    if success:
                        LeadActivity.objects.create(
                            lead=lead,
                            activity_type=LeadActivity.TYPE_WHATSAPP_SENT,
                            description="AI sent message via WhatsApp",
                            metadata={'text': message[:500], 'is_ai_action': True}
                        )

                if success:
                    # Update last contacted
                    lead.last_contacted = timezone.now().date()
                    lead.save(update_fields=['last_contacted'])
                    return channel_name, True

            except Exception as e:
                logger.error(f"Error sending via {channel_name}: {e}")
                continue

        return 'none', False

    def create_auto_task(
        self,
        lead: Lead,
        title: str,
        task_type: str,
        execution_type: str,
        days_due: int = 1,
        description: str = '',
        execution_content: str = ''
    ) -> Task:
        """
        Create an auto-executable task for a lead.

        Returns the created task.
        """
        task = Task.objects.create(
            lead=lead,
            title=title,
            description=description,
            task_type=task_type,
            due_date=timezone.now().date() + timezone.timedelta(days=days_due),
            is_auto_executable=True,
            execution_type=execution_type,
            execution_content=execution_content,
            is_ai_generated=True,
        )

        # Log activity
        LeadActivity.objects.create(
            lead=lead,
            activity_type=LeadActivity.TYPE_TASK_CREATED,
            description=f"AI created auto-task: {title}",
            metadata={
                'task_id': task.id,
                'task_title': title,
                'execution_type': execution_type,
                'is_auto_executable': True,
                'is_ai_generated': True,
            }
        )

        logger.info(f"Created auto-task '{title}' for lead {lead.id}")
        return task

    def execute_pending_tasks_for_lead(self, lead: Lead) -> int:
        """
        Execute all pending auto-tasks for a lead.

        Returns count of successfully executed tasks.
        """
        tasks = self.get_pending_auto_tasks(lead)
        executed_count = 0

        for task in tasks:
            if self.execute_task(task):
                executed_count += 1

        return executed_count


# Singleton instance
task_executor = TaskExecutor()
