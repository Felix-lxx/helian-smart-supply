"""Explicit company delegation. Membership never grants platform administration."""
from .models import CompanyMember


def supplier_ids(user, action='read'):
    jobs={'read':['manager','quality','dispatch','viewer'],
          'manage':['manager'],'inspect':['manager','quality'],
          'dispatch':['manager','dispatch']}.get(action,[])
    ids={user.id}
    if user.role=='supplier':
        ids.update(CompanyMember.objects.filter(user=user,job__in=jobs,company__owner__role='supplier').values_list('company__owner_id',flat=True))
    return ids


def buyer_ids(user, action='read'):
    jobs = {'read': ['manager', 'buyer', 'dispatch', 'viewer'],
            'manage': ['manager', 'buyer'], 'receive': ['manager', 'buyer', 'dispatch']}.get(action, [])
    ids = {user.id}
    if user.role == 'retail':
        ids.update(CompanyMember.objects.filter(user=user, job__in=jobs,
            company__owner__role='retail').values_list('company__owner_id', flat=True))
    return ids


def participant_ids(user, action='manage'):
    return supplier_ids(user, action) | buyer_ids(user, action)
