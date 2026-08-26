from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from core.utils import get_safe_next_or_referer
from django.urls import reverse

from .forms import VehicleDocumentForm
from .models import Vehicle, VehicleDocument


@login_required(login_url='/login/')
def vehicle_documents(request, vehicle_id):
    """
    Ek vehicle ke saare documents — list + add/edit/delete.
    Add/Edit/Delete sirf superuser (Admin) kar sakta hai.
    """
    vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
    documents = vehicle.documents.all()
    editing = None

    # Edit mode: ?doc=<id>
    doc_id = request.GET.get('doc', '').strip()
    if doc_id.isdigit():
        editing = documents.filter(pk=int(doc_id)).first()

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'delete':
            if not request.user.is_superuser:
                messages.error(request, 'Sirf Admin document delete kar sakta hai.')
            else:
                doc = get_object_or_404(VehicleDocument, pk=request.POST.get('doc_id'))
                doc.delete()
                messages.success(request, f'{doc.get_doc_type_display()} document delete ho gaya!')
            return redirect('vehicles:documents', vehicle_id=vehicle.id)

        # ---- save (add or edit) ----
        if not request.user.is_superuser:
            messages.error(request, 'Sirf Admin documents add/change kar sakta hai.')
            return redirect('vehicles:documents', vehicle_id=vehicle.id)

        is_edit = bool(editing and request.POST.get('doc_id'))
        if is_edit:
            instance = editing
            # Edit mode me vehicle select DISABLED hota hai — disabled inputs
            # POST me value nahi bhejte, isliye instance ka vehicle hi inject karo
            data = request.POST.copy()
            data['vehicle'] = instance.vehicle_id
            form = VehicleDocumentForm(data, request.FILES, instance=instance)
        else:
            instance = VehicleDocument(vehicle=vehicle)
            form = VehicleDocumentForm(request.POST, request.FILES, instance=instance)

        if form.is_valid():
            form.save()
            messages.success(request, f'{instance.get_doc_type_display()} document save ho gaya!')
            return redirect('vehicles:documents', vehicle_id=vehicle.id)
        else:
            err_list = [f"{f}: {', '.join(e)}" for f, e in form.errors.items()]
            messages.error(request, '; '.join(err_list))
            # Invalid par bhi edit form par hi wapas jao (blank add form na khule)
            if is_edit:
                return redirect(f'/vehicles/{vehicle.id}/documents/?doc={editing.pk}')

    form = VehicleDocumentForm(instance=editing, initial={'vehicle': vehicle})
    if editing:
        form.fields['vehicle'].disabled = True

    context = {
        'vehicle': vehicle,
        'documents': documents,
        'form': form,
        'editing': editing,
        'back_url': get_safe_next_or_referer(request, reverse('core:vehicle_report')),
    }
    return render(request, 'vehicles/vehicle_documents.html', context)


@login_required(login_url='/login/')
def all_vehicle_documents(request):
    """
    SAARE vehicles ki document summary — bina trips wale vehicles bhi.
    Vehicle Report page ke 'All Vehicle Documents' button se aate hain.
    """
    from datetime import timedelta
    from django.utils import timezone

    today = timezone.localdate()
    rows = []

    for v in Vehicle.objects.all().order_by('registration_number'):
        docs = v.documents.all()
        nearest = docs.order_by('expiry_date').first()
        urgent = docs.filter(
            expiry_date__lte=today + timedelta(days=30)
        ).count()
        rows.append({
            'vehicle': v,
            'docs_count': docs.count(),
            'nearest_expiry': nearest.expiry_date if nearest else None,
            'nearest_type': nearest.get_doc_type_display() if nearest else '',
            'days_left': (nearest.expiry_date - today).days if nearest else None,
            'urgency': nearest.urgency if nearest else 'none',
            'urgent_count': urgent,
        })

    # Back hamesha Vehicle Report par (referer-based nahi — warna
    # documents <-> all-documents loop ban jaata hai)
    from core.utils import get_safe_next
    back_url = get_safe_next(request, reverse('core:vehicle_report'))

    return render(request, 'vehicles/all_documents.html', {
        'rows': rows,
        'back_url': back_url,
    })
