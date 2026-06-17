"""
Delete expired communication media files.

The command intentionally deletes only files referenced by old LeadActivity
metadata. It never recursively cleans a whole media directory.
"""
from __future__ import annotations

import os
from datetime import timedelta
from urllib.parse import unquote, urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.leads.models import LeadActivity


ALLOWED_MEDIA_SUBDIRS = ('comms_media', 'incoming_media', 'incoming_photos')


def _real_path(path: str) -> str:
    return os.path.realpath(os.path.abspath(path))


def _is_inside_dir(path: str, directory: str) -> bool:
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:
        return False


class Command(BaseCommand):
    help = 'Delete communication media files referenced by LeadActivity records older than N days.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Keep media for this many days before deleting it. Default: 30.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without removing files.',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        if days < 1:
            raise CommandError('--days must be at least 1')

        cutoff = timezone.now() - timedelta(days=days)
        allowed_dirs = tuple(
            _real_path(os.path.join(settings.MEDIA_ROOT, subdir))
            for subdir in ALLOWED_MEDIA_SUBDIRS
        )

        seen_paths: set[str] = set()
        deleted = 0
        missing = 0
        skipped = 0
        errors = 0

        activities = (
            LeadActivity.objects
            .filter(created_at__lt=cutoff)
            .exclude(metadata__isnull=True)
            .only('id', 'metadata')
            .iterator(chunk_size=500)
        )

        for activity in activities:
            for file_url in self._extract_file_urls(activity.metadata):
                file_path = self._file_url_to_path(file_url)
                if not file_path:
                    skipped += 1
                    continue

                if file_path in seen_paths:
                    continue
                seen_paths.add(file_path)

                if not any(_is_inside_dir(file_path, allowed_dir) for allowed_dir in allowed_dirs):
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Skipped outside allowed dirs: {file_url}'))
                    continue

                if not os.path.exists(file_path):
                    missing += 1
                    continue

                if not os.path.isfile(file_path):
                    skipped += 1
                    self.stdout.write(self.style.WARNING(f'Skipped non-file path: {file_path}'))
                    continue

                if dry_run:
                    deleted += 1
                    self.stdout.write(f'Would delete: {file_path}')
                    continue

                try:
                    os.remove(file_path)
                    deleted += 1
                    self.stdout.write(f'Deleted: {file_path}')
                except OSError as exc:
                    errors += 1
                    self.stdout.write(self.style.ERROR(f'Failed to delete {file_path}: {exc}'))

        action = 'Would delete' if dry_run else 'Deleted'
        self.stdout.write(self.style.SUCCESS(
            f'{action} {deleted} expired media file(s); '
            f'missing={missing}; skipped={skipped}; errors={errors}; retention_days={days}'
        ))

    def _extract_file_urls(self, metadata) -> list[str]:
        if not isinstance(metadata, dict):
            return []

        urls: list[str] = []
        file_url = metadata.get('file_url')
        if isinstance(file_url, str) and file_url.strip():
            urls.append(file_url.strip())

        file_urls = metadata.get('file_urls')
        if isinstance(file_urls, list):
            urls.extend(url.strip() for url in file_urls if isinstance(url, str) and url.strip())

        return urls

    def _file_url_to_path(self, file_url: str) -> str | None:
        parsed = urlparse(file_url)
        raw_path = parsed.path if parsed.scheme or parsed.netloc else file_url
        media_url = settings.MEDIA_URL or '/media/'

        if not raw_path.startswith(media_url):
            return None

        relative_path = unquote(raw_path[len(media_url):]).lstrip('/\\')
        if not relative_path:
            return None

        return _real_path(os.path.join(settings.MEDIA_ROOT, relative_path))
