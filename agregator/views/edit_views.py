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

from agregator.decorators import owner_or_admin_required
from agregator.models import Act, ScientificReport, TechReport, OpenLists, ArchaeologicalHeritageSite, \
    IdentifiedArchaeologicalHeritageSite, ObjectAccountCard, CommercialOffers, GeoObject
from agregator.processing.coordinates_extraction import process_coords_from_edit_page
from agregator.views import process_edit_form, process_supplement


@login_required
@owner_or_admin_required(Act)
def acts_edit(request, pk):
    act = get_object_or_404(Act, id=pk)
    if request.method == 'POST':
        fields = [
            'year',
            'finish_date',
            'type',
            'name_number',
            'place',
            'customer',
            'area',
            'expert',
            'executioner',
            'open_list',
            'conclusion',
            'border_objects'
        ]
        try:
            process_edit_form(request, act, fields)
            act.coordinates = process_coords_from_edit_page(request, act)
            act.supplement = process_supplement(request, act)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'act_edit.html', {'report': act})

        act.save()
        messages.success(request, 'Акт успешно обновлен.')
        return redirect(f'/acts/{act.id}')  # Перенаправление на страницу профиля

    return render(request, 'act_edit.html', {'report': act})


@login_required
@owner_or_admin_required(Act)
def acts_delete(request, pk):
    act_instance = get_object_or_404(Act, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            act_instance.delete()
        else:
            act_instance._raw_delete = True
            super(Act, act_instance).delete()
    return redirect(f'acts_register')


@login_required
@owner_or_admin_required(ScientificReport)
def scientific_reports_edit(request, pk):
    report = get_object_or_404(ScientificReport, id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'organization',
            'author',
            'open_list',
            'writing_date',
            'introduction',
            'contractors',
            'place',
            'area_info',
            'research_history',
            'results',
            'conclusion'
        ]
        try:
            process_edit_form(request, report, fields)
            report.coordinates = process_coords_from_edit_page(request, report)
            report.supplement = process_supplement(request, report)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'scientific_report_edit.html', {'report': report})

        report.save()
        messages.success(request, 'Отчёт успешно обновлен.')
        return redirect(f'/scientific_reports/{report.id}')

    return render(request, 'scientific_report_edit.html', {'report': report})


@login_required
@owner_or_admin_required(ScientificReport)
def scientific_reports_delete(request, pk):
    report_instance = get_object_or_404(ScientificReport, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            report_instance.delete()
        else:
            report_instance._raw_delete = True
            super(ScientificReport, report_instance).delete()
    return redirect(f'scientific_reports_register')


@login_required
@owner_or_admin_required(TechReport)
def tech_reports_edit(request, pk):
    report = get_object_or_404(TechReport, id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'organization',
            'author',
            'open_list',
            'writing_date',
            'introduction',
            'contractors',
            'place',
            'area_info',
            'research_history',
            'results',
            'conclusion'
        ]
        try:
            process_edit_form(request, report, fields)
            report.coordinates = process_coords_from_edit_page(request, report)
            report.supplement = process_supplement(request, report)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'tech_report_edit.html', {'report': report})

        report.save()
        messages.success(request, 'Отчёт успешно обновлен.')
        return redirect(f'/tech_reports/{report.id}')

    return render(request, 'tech_report_edit.html', {'report': report})


@login_required
@owner_or_admin_required(TechReport)
def tech_reports_delete(request, pk):
    report_instance = get_object_or_404(TechReport, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            report_instance.delete()
        else:
            report_instance._raw_delete = True
            super(TechReport, report_instance).delete()
    return redirect(f'tech_reports_register')


@login_required
@owner_or_admin_required(OpenLists)
def open_lists_edit(request, pk):
    open_list = get_object_or_404(OpenLists, id=pk)
    if request.method == 'POST':
        fields = [
            'number',
            'holder',
            'object',
            'works',
            'start_date',
            'end_date'
        ]

        try:
            process_edit_form(request, open_list, fields)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'open_list_edit.html', {'open_list': open_list})

        open_list.save()
        messages.success(request, 'Открытый лист успешно обновлен.')
        return redirect(f'/open_lists/{open_list.id}')

    return render(request, 'open_list_edit.html', {'open_list': open_list})


@login_required
@owner_or_admin_required(OpenLists)
def open_lists_delete(request, pk):
    list_instance = get_object_or_404(OpenLists, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            list_instance.delete()
        else:
            list_instance._raw_delete = True
            super(OpenLists, list_instance).delete()
    return redirect(f'open_lists_register')


@login_required
@owner_or_admin_required(ArchaeologicalHeritageSite)
def archaeological_heritage_sites_edit(request, pk):
    oan = get_object_or_404(ArchaeologicalHeritageSite, id=pk)
    if request.method == 'POST':
        fields = [
            'doc_name',
            'district',
            'document',
            'register_num',
            'is_excluded'
        ]

        try:
            process_edit_form(request, oan, fields)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'archaeological_heritage_site_edit.html', {'archaeological_heritage_site': oan})

        messages.success(request, 'Памятник успешно обновлен.')
        return redirect(f'/archaeological_heritage_sites/{oan.id}')

    return render(request, 'archaeological_heritage_site_edit.html', {'archaeological_heritage_site': oan})


@login_required
@owner_or_admin_required(IdentifiedArchaeologicalHeritageSite)
def identified_archaeological_heritage_sites_edit(request, pk):
    voan = get_object_or_404(IdentifiedArchaeologicalHeritageSite, id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'address',
            'obj_info',
            'document',
            'is_excluded'
        ]

        try:
            process_edit_form(request, voan, fields)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'identified_archaeological_heritage_site_edit.html',
                          {'identified_archaeological_heritage_site': voan})

        messages.success(request, 'Памятник успешно обновлен.')
        return redirect(f'/identified_archaeological_heritage_sites/{voan.id}')

    return render(request, 'identified_archaeological_heritage_site_edit.html',
                  {'identified_archaeological_heritage_site': voan})


@login_required
@owner_or_admin_required(ArchaeologicalHeritageSite)
def archaeological_heritage_sites_delete(request, pk):
    oan = get_object_or_404(ArchaeologicalHeritageSite, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            oan.delete()
        else:
            oan._raw_delete = True
            super(ArchaeologicalHeritageSite, oan).delete()
    return redirect(f'archaeological_heritage_sites_register')


@login_required
@owner_or_admin_required(IdentifiedArchaeologicalHeritageSite)
def identified_archaeological_heritage_sites_delete(request, pk):
    voan = get_object_or_404(IdentifiedArchaeologicalHeritageSite, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            voan.delete()
        else:
            voan._raw_delete = True
            super(IdentifiedArchaeologicalHeritageSite, voan).delete()
    return redirect(f'identified_archaeological_heritage_sites_register')


@login_required
@owner_or_admin_required(ObjectAccountCard)
def account_cards_edit(request, pk):
    account_card = get_object_or_404(ObjectAccountCard, id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'creation_time',
            'address',
            'object_type',
            'general_classification',
            'description',
            'usage',
            'discovery_info'
        ]
        try:
            process_edit_form(request, account_card, fields)
            account_card.supplement = process_supplement(request, account_card)
            account_card.coordinates = process_coords_from_edit_page(request, account_card)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'account_card_edit.html', {'account_card': account_card})

        account_card.save()
        messages.success(request, 'Учётная карта успешно обновлена.')
        return redirect(f'/account_cards/{account_card.id}')

    return render(request, 'account_card_edit.html', {'account_card': account_card})


@login_required
@owner_or_admin_required(ObjectAccountCard)
def account_cards_delete(request, pk):
    account_card_instance = get_object_or_404(ObjectAccountCard, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            account_card_instance.delete()
        else:
            account_card_instance._raw_delete = True
            super(ObjectAccountCard, account_card_instance).delete()
    return redirect(f'account_cards_register')


@login_required
@owner_or_admin_required(CommercialOffers)
def commercial_offers_edit(request, pk):
    commercial_offer = get_object_or_404(CommercialOffers, id=pk)
    commercial_offer.coordinates = commercial_offer.coordinates_dict
    if request.method == 'POST':

        try:
            commercial_offer.coordinates = process_coords_from_edit_page(request, commercial_offer)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'commercial_offer_edit.html',
                          {'commercial_offer': commercial_offer})

        commercial_offer.save()
        messages.success(request, 'Коммерческое предложение успешно обновлено.')
        return redirect(f'/commercial_offers_edit/{commercial_offer.id}')

    return render(request, 'commercial_offer_edit.html',
                  {'commercial_offer': commercial_offer})


@login_required
@owner_or_admin_required(CommercialOffers)
def commercial_offers_delete(request, pk):
    commercial_offer_instance = get_object_or_404(CommercialOffers, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            commercial_offer_instance.delete()
        else:
            commercial_offer_instance._raw_delete = True
            super(CommercialOffers, commercial_offer_instance).delete()
    return redirect(f'commercial_offers_register')


@login_required
@owner_or_admin_required(GeoObject)
def geo_objects_edit(request, pk):
    geo_object = get_object_or_404(GeoObject, id=pk)
    geo_object.coordinates = geo_object.coordinates_dict
    if request.method == 'POST':

        try:
            geo_object.coordinates = process_coords_from_edit_page(request, geo_object)
        except Exception as e:
            messages.error(request, f'Ошибка при обновлении: {str(e)}')
            return render(request, 'geo_object_edit.html',
                          {'geo_object': geo_object})

        geo_object.save()
        messages.success(request, 'Коммерческое предложение успешно обновлено.')
        return redirect(f'/geo_objects_edit/{geo_object.id}')

    return render(request, 'geo_object_edit.html',
                  {'geo_object': geo_object})


@login_required
@owner_or_admin_required(GeoObject)
def geo_objects_delete(request, pk):
    geo_object = get_object_or_404(GeoObject, id=pk)
    if request.method == 'POST':
        delete_files_flag = request.POST.get('delete_files') == 'on'
        if delete_files_flag:
            geo_object.delete()
        else:
            geo_object._raw_delete = True
            super(GeoObject, geo_object).delete()
    return redirect(f'geo_objects_register')
