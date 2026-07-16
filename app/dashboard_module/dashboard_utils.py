"""Utility functions for Dashboard module."""

from typing import List, Dict, Any
from datetime import datetime
from service_utils.db_utils.pg_db import PostgresDB
from service_utils.log_management import get_logger

logger = get_logger(__name__)


def get_category_stats() -> Dict[str, Any]:
    """Get top-level stat card numbers for the category dashboard."""
    try:
        db = PostgresDB()

        categories = db.read(
            'categories',
            conditions={'is_root': False, 'is_active': True, 'deleted_on': None},
            columns=['id']
        )
        total_categories = len(categories) if categories else 0

        pages = db.read('pages', conditions={'deleted_on': None}, columns=['id'])
        total_pages = len(pages) if pages else 0

        content = db.read('content', conditions={'deleted_on': None}, columns=['page_id'])
        pages_with_content = set()
        for item in (content or []):
            pid = item.get('page_id')
            if pid:
                pages_with_content.add(pid)
        pages_needing_attention = max(total_pages - len(pages_with_content), 0)

        pending = db.read(
            'content',
            conditions={'deleted_on': None, 'approval_status': 'PENDING'},
            columns=['id']
        )
        pending_approvals = len(pending) if pending else 0

        return {
            'total_categories': total_categories,
            'total_pages': total_pages,
            'pages_needing_attention': pages_needing_attention,
            'pending_approvals': pending_approvals,
        }

    except Exception as e:
        logger.error(f"Error getting category stats: {e}")
        return {
            'total_categories': 0,
            'total_pages': 0,
            'pages_needing_attention': 0,
            'pending_approvals': 0,
        }


def get_category_breakdown() -> List[Dict[str, Any]]:
    """
    Build per-category breakdown: page counts, content counts, approval rates.
    Returns list sorted by total_pages descending.
    """
    try:
        db = PostgresDB()

        categories = db.read(
            'categories',
            conditions={'is_root': False, 'is_active': True, 'deleted_on': None},
            columns=['id', 'category_name']
        )
        if not categories:
            return []

        pages = db.read('pages', conditions={'deleted_on': None}, columns=['id', 'category_id'])
        content = db.read('content', conditions={'deleted_on': None}, columns=['page_id', 'approval_status'])

        # Map: category_id -> set of page_ids
        category_page_ids: Dict[int, set] = {}
        for page in (pages or []):
            cat_id = page.get('category_id')
            if cat_id:
                if cat_id not in category_page_ids:
                    category_page_ids[cat_id] = set()
                category_page_ids[cat_id].add(page['id'])

        # Map: page_id -> content count, approved count
        page_content_count: Dict[int, int] = {}
        page_approved_count: Dict[int, int] = {}
        for item in (content or []):
            pid = item.get('page_id')
            if pid:
                page_content_count[pid] = page_content_count.get(pid, 0) + 1
                status = item.get('approval_status')
                if hasattr(status, 'value'):
                    status = status.value
                if status == 'APPROVED':
                    page_approved_count[pid] = page_approved_count.get(pid, 0) + 1

        result = []
        for cat in categories:
            cat_id = cat['id']
            cat_page_ids = category_page_ids.get(cat_id, set())
            total_pages = len(cat_page_ids)
            pages_with_content = sum(1 for pid in cat_page_ids if page_content_count.get(pid, 0) > 0)
            pages_empty = total_pages - pages_with_content
            total_content = sum(page_content_count.get(pid, 0) for pid in cat_page_ids)
            approved_count = sum(page_approved_count.get(pid, 0) for pid in cat_page_ids)
            approval_rate = round(approved_count / total_content * 100) if total_content > 0 else 0

            result.append({
                'category_id': cat_id,
                'category_name': cat['category_name'],
                'total_pages': total_pages,
                'pages_with_content': pages_with_content,
                'pages_empty': pages_empty,
                'total_content': total_content,
                'approved_count': approved_count,
                'approval_rate': approval_rate,
            })

        # Sort by the nav order: Understanding, Projects, Resources, Policy, Lots, Newsletter, Social Media
        nav_order = ['Understanding', 'Projects', 'Resources', 'Policy', 'Lots', 'Newsletter', 'Social Media']
        def nav_sort_key(item):
            name = item['category_name']
            for i, n in enumerate(nav_order):
                if n.lower() in name.lower():
                    return i
            return len(nav_order)
        result.sort(key=nav_sort_key)
        return result

    except Exception as e:
        logger.error(f"Error getting category breakdown: {e}")
        return []


def get_pages_needing_attention(limit: int = 8) -> List[Dict[str, Any]]:
    """Return pages that have no content yet, with their category name."""
    try:
        db = PostgresDB()

        pages = db.read(
            'pages',
            conditions={'deleted_on': None, 'is_active': True},
            columns=['id', 'page_name', 'category_id']
        )
        if not pages:
            return []

        content = db.read('content', conditions={'deleted_on': None}, columns=['page_id'])
        pages_with_content = set()
        for item in (content or []):
            pid = item.get('page_id')
            if pid:
                pages_with_content.add(pid)

        categories = db.read('categories', conditions={'deleted_on': None}, columns=['id', 'category_name'])
        cat_map = {c['id']: c['category_name'] for c in (categories or [])}

        attention = []
        for page in pages:
            if page['id'] not in pages_with_content:
                attention.append({
                    'page_id': page['id'],
                    'page_name': page['page_name'],
                    'category_name': cat_map.get(page.get('category_id'), 'Uncategorized'),
                })
            if len(attention) >= limit:
                break

        return attention

    except Exception as e:
        logger.error(f"Error getting pages needing attention: {e}")
        return []


def get_recent_activity(limit: int = 6) -> List[Dict[str, Any]]:
    """Recent content activity with category context."""
    try:
        db = PostgresDB()

        recent_content = db.read(
            'content',
            conditions={'deleted_on': None},
            columns=['id', 'page_id', 'content_type', 'approval_status', 'action', 'created_on'],
            order_by=[('created_on', False)],
            limit=limit
        )
        if not recent_content:
            return []

        pages = db.read('pages', conditions={'deleted_on': None}, columns=['id', 'page_name', 'category_id'])
        page_map = {}
        if pages:
            page_map = {p['id']: {'name': p['page_name'], 'category_id': p.get('category_id')} for p in pages}

        categories = db.read('categories', conditions={'deleted_on': None}, columns=['id', 'category_name'])
        cat_map = {c['id']: c['category_name'] for c in (categories or [])}

        activities = []
        now = datetime.now()

        for item in recent_content:
            page_info = page_map.get(item.get('page_id'), {})
            page_name = page_info.get('name', 'Unknown Page')
            cat_id = page_info.get('category_id')
            category_name = cat_map.get(cat_id, '') if cat_id else ''

            content_type = item.get('content_type')
            if hasattr(content_type, 'value'):
                content_type = content_type.value
            content_type = content_type if content_type else 'Content'

            action = item.get('action')
            if hasattr(action, 'value'):
                action = action.value

            if action == 'NEW':
                title = f"Generated {content_type.lower()} for {page_name}"
            elif action == 'DRAFT':
                title = f"Drafted {content_type.lower()} for {page_name}"
            elif action == 'RE_RUN':
                title = f"Re-generated {content_type.lower()} for {page_name}"
            else:
                title = f"Updated {content_type.lower()} for {page_name}"

            status = item.get('approval_status')
            if hasattr(status, 'value'):
                status = status.value
            status = status if status else 'PENDING'

            activities.append({
                'title': title,
                'category_name': category_name,
                'status': status,
                'time_ago': _get_relative_time(item.get('created_on'), now),
            })

        return activities

    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return []


def _get_relative_time(dt: datetime, now: datetime) -> str:
    """Convert a datetime to a relative time string like '2 min ago'."""
    if not dt:
        return "Unknown"
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins} min ago" if mins == 1 else f"{mins} mins ago"
    elif seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    elif seconds < 604800:
        days = seconds // 86400
        return f"{days} day ago" if days == 1 else f"{days} days ago"
    else:
        weeks = seconds // 604800
        return f"{weeks} week ago" if weeks == 1 else f"{weeks} weeks ago"
