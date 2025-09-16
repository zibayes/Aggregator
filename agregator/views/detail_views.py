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


def acts(request, pk):
    act = get_object_or_404(Act, id=pk)
    return render(request, 'act.html', {'report': act})


def scientific_reports(request, pk):
    report = get_object_or_404(ScientificReport, id=pk)
    return render(request, 'scientific_report.html', {'report': report})


def tech_reports(request, pk):
    report = get_object_or_404(TechReport, id=pk)
    return render(request, 'tech_report.html', {'report': report})


def open_lists(request, pk):
    open_list = get_object_or_404(OpenLists, id=pk)
    return render(request, 'open_list.html', {'open_list': open_list})


def archaeological_heritage_site(request, pk):
    oan = get_object_or_404(ArchaeologicalHeritageSite, id=pk)
    return render(request, 'archaeological_heritage_site.html', {'archaeological_heritage_site': oan})


def identified_archaeological_heritage_site(request, pk):
    voan = get_object_or_404(IdentifiedArchaeologicalHeritageSite, id=pk)
    return render(request, 'identified_archaeological_heritage_site.html',
                  {'identified_archaeological_heritage_site': voan})


def account_cards(request, pk):
    account_card = get_object_or_404(ObjectAccountCard, id=pk)
    heritage = IdentifiedArchaeologicalHeritageSite.objects.filter(account_card__id=pk, name=account_card.name)
    if not heritage:
        heritage = ArchaeologicalHeritageSite.objects.filter(account_card__id=pk, doc_name=account_card.name)
        if heritage:
            account_card.heritage_url = '/archaeological_heritage_sites/'
    else:
        account_card.heritage_url = '/identified_archaeological_heritage_sites/'
    if heritage:
        account_card.heritage_url += str(heritage[0].id) + '/'
        account_card.heritage_source = heritage[0].source
    return render(request, 'account_card.html', {'account_card': account_card})
