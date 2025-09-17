import json
import os
from urllib.parse import quote

import pandas as pd
import simplekml
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from pyproj import Geod
from rest_framework import generics
from shapely.geometry import Polygon, LineString
from shapely.geometry import shape, Point
from shapely.ops import nearest_points
from agregator.models import Act, ScientificReport, TechReport, OpenLists, ArchaeologicalHeritageSite, \
    IdentifiedArchaeologicalHeritageSite, ObjectAccountCard
from django.http import Http404
from django.urls import reverse


def acts(request, pk):
    try:
        act = get_object_or_404(Act, id=pk)
    except Exception:
        raise Http404
    return render(request, 'act.html', {'report': act})


def scientific_reports(request, pk):
    try:
        report = get_object_or_404(ScientificReport, id=pk)
    except Exception:
        raise Http404
    return render(request, 'scientific_report.html', {'report': report})


def tech_reports(request, pk):
    try:
        report = get_object_or_404(TechReport, id=pk)
    except Exception:
        raise Http404
    return render(request, 'tech_report.html', {'report': report})


def open_lists(request, pk):
    try:
        open_list = get_object_or_404(OpenLists, id=pk)
    except Exception:
        raise Http404
    return render(request, 'open_list.html', {'open_list': open_list})


def archaeological_heritage_sites(request, pk):
    try:
        oan = get_object_or_404(ArchaeologicalHeritageSite, id=pk)
    except Exception:
        raise Http404
    return render(request, 'archaeological_heritage_site.html', {'archaeological_heritage_site': oan})


def identified_archaeological_heritage_sites(request, pk):
    try:
        voan = get_object_or_404(IdentifiedArchaeologicalHeritageSite, id=pk)
    except Exception:
        raise Http404
    return render(request, 'identified_archaeological_heritage_site.html',
                  {'identified_archaeological_heritage_site': voan})


def account_cards(request, pk):
    try:
        account_card = get_object_or_404(ObjectAccountCard, id=pk)
    except Exception:
        raise Http404

    account_card.heritage_url = None

    heritage = (IdentifiedArchaeologicalHeritageSite.objects.filter(account_card=account_card).first() or
                ArchaeologicalHeritageSite.objects.filter(account_card=account_card).first())

    if heritage:
        account_card.heritage_url = reverse(
            'identified_archaeological_heritage_sites' if isinstance(heritage, IdentifiedArchaeologicalHeritageSite)
            else 'archaeological_heritage_sites',
            kwargs={'pk': heritage.id}
        )
        account_card.heritage_source = heritage.source

    return render(request, 'account_card.html', {
        'account_card': account_card,
        'heritage': heritage
    })
