# -*- coding: utf-8 -*-
#
# Copyright (C) 2011-2013 Carlos Flores <cafg10@gmail.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library. If not, see <http://www.gnu.org/licenses/>.

from collections import defaultdict
from datetime import datetime, time
from decimal import Decimal

from constance import config
from django.contrib import messages
from django.db import models
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import (CreateView, UpdateView, TemplateView,
                                  DetailView, ListView, RedirectView,
                                  DeleteView)
from django.forms.models import inlineformset_factory
from django.contrib.auth.decorators import permission_required

from spital.forms import DepositoForm
from users.mixins import LoginRequiredMixin, CurrentUserFormMixin
from spital.models import Admision, Deposito
from emergency.models import Emergencia
from imaging.models import Examen
from persona.models import Persona
from invoice.models import (Recibo, Venta, Pago, TurnoCaja, CierreTurno,
                            TipoPago, dot01)
from invoice.forms import (ReciboForm, VentaForm, PeriodoForm,
                           EmergenciaFacturarForm, AdmisionFacturarForm,
                           CorteForm, ExamenFacturarForm, InventarioForm,
                           PagoForm, PersonaForm, TurnoCajaForm,
                           CierreTurnoForm, TurnoCajaCierreForm,
                           VentaPeriodoForm, PeriodoAreaForm)
from inventory.models import ItemTemplate


class InvoicePermissionMixin(LoginRequiredMixin):
    @method_decorator(permission_required('invoice.cajero'))
    def dispatch(self, *args, **kwargs):
        return super(InvoicePermissionMixin, self).dispatch(*args, **kwargs)


class IndexView(TemplateView, InvoicePermissionMixin):
    """Muestra las opciones disponibles para la aplicación"""

    template_name = 'invoice/index.html'

    def create_periodo_form(self, context, object_name, prefix, legend, action):
        context[object_name] = PeriodoForm(prefix=prefix)
        context[object_name].set_legend(legend)
        context[object_name].set_action(action)

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Recibo`"""

        context = super(IndexView, self).get_context_data(**kwargs)
        self.create_periodo_form(context, 'reciboperiodoform', 'recibo',
                                 u'Recibos de un Periodo', 'invoice-periodo')

        self.create_periodo_form(context, 'recibodetailform', 'recibodetail',
                                 u'Detalle de Recibos de un Periodo',
                                 'invoice-periodo-detail')

        self.create_periodo_form(context, 'tipoform', 'tipo',
                                 u'Productos por Área y Periodo',
                                 'invoice-tipo')

        self.create_periodo_form(context, 'productoperiodoform', 'producto',
                                 u'Productos Facturados en un Periodo',
                                 'invoice-periodo-producto')

        self.create_periodo_form(context, 'remiteperiodoform', 'remite',
                                 u'Referencias de un Periodo',
                                 'invoice-periodo-remite')

        self.create_periodo_form(context, 'radperiodoform', 'rad',
                                 u'Comisiones de un Periodo',
                                 'invoice-periodo-radiologo')

        self.create_periodo_form(context, 'emerperiodoform', 'emergencia',
                                 u'Emergencias de un Periodo',
                                 'invoice-periodo-emergencia')

        context['corteform'] = CorteForm(prefix='corte')
        context['corteform'].set_action('invoice-corte')

        context['inventarioform'] = InventarioForm(prefix='inventario')
        context['inventarioform'].set_action('invoice-inventario')

        context['examenes'] = Examen.objects.filter(facturado=False).order_by(
            '-id')
        context['admisiones'] = Admision.objects.filter(facturada=False)
        context['emergencias'] = Emergencia.objects.filter(
            facturada=False).order_by('id')

        context['turnos'] = TurnoCaja.objects.filter(usuario=self.request.user,
                                                     finalizado=False).all()

        context['ventaperiodoform'] = VentaPeriodoForm(prefix='venta')
        context['ventaperiodoform'].set_action('periodo-venta')

        context['ventaareaperiodoform'] = PeriodoAreaForm(prefix='venta-area')
        context['ventaareaperiodoform'].set_action('periodo-venta-area')

        return context


class ReciboPersonaCreateView(CreateView, LoginRequiredMixin):
    """Permite crear un :class:`Recibo` utilizando una :class:`Persona`
    existente en la aplicación"""

    model = Recibo
    form_class = ReciboForm
    template_name = 'invoice/recibo_persona_create.html'

    def get_form_kwargs(self):
        """Registra el :class:`User` que esta creando el :class:`Recibo`"""

        kwargs = super(ReciboPersonaCreateView, self).get_form_kwargs()
        kwargs.update({'initial': {'cajero': self.request.user.id,
                                   'cliente': self.persona.id}})
        return kwargs

    def dispatch(self, *args, **kwargs):
        """Obtiene el :class:`Recibo` que se entrego como argumento en la
        url"""

        self.persona = get_object_or_404(Persona, pk=kwargs['persona'])
        return super(ReciboPersonaCreateView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReciboPersonaCreateView, self).get_context_data(
            **kwargs)
        context['persona'] = self.persona
        return context


class ReciboCreateView(CreateView, LoginRequiredMixin):
    """Permite crear un :class:`Recibo` al mismo tiempo que se crea una
    :class:`Persona`, utiliza un formulario simplificado que requiere
    unicamente indicar el nombre y apellidos del cliente, que aún así son
    opcionales.
    """
    model = Recibo

    def dispatch(self, request, *args, **kwargs):

        self.persona = Persona()
        self.ReciboFormset = inlineformset_factory(Persona, Recibo,
                                                   form=ReciboForm,
                                                   fk_name='cliente', extra=1)
        return super(CreateView, self).dispatch(request, *args, **kwargs)

    def get_form(self, form_class):

        self.persona_form = PersonaForm(instance=self.persona, prefix='persona')
        self.persona_form.helper.form_tag = False
        formset = self.ReciboFormset(instance=self.persona, prefix='recibo')
        return formset

    def get_context_data(self, **kwargs):

        context = super(ReciboCreateView, self).get_context_data(**kwargs)
        context['persona_form'] = self.persona_form
        return context

    def post(self, request, *args, **kwargs):
        self.form = PersonaForm(request.POST, request.FILES,
                                instance=self.persona,
                                prefix='persona')
        self.formset = self.ReciboFormset(request.POST, request.FILES,
                                          instance=self.persona,
                                          prefix='recibo')

        if self.form.is_valid() and self.formset.is_valid():
            self.form.save()
            instances = self.formset.save()
            for instance in instances:
                self.recibo = instance
                self.recibo.cajero = self.request.user
                self.recibo.save()

            return self.form_valid(self.formset)
        else:
            return self.form_invalid(self.formset)

    def get_success_url(self):

        return reverse('invoice-view-id', args=[self.recibo.id])


class ReciboExamenCreateView(CreateView, LoginRequiredMixin):
    """Permite crear un :class:`Recibo` utilizando una :class:`Persona`
    existente en la aplicación"""

    model = Recibo
    form_class = ReciboForm
    template_name = 'invoice/recibo_persona_create.html'

    def get_form_kwargs(self):
        """Registra el :class:`User` que esta creando el :class:`Recibo`"""

        kwargs = super(ReciboExamenCreateView, self).get_form_kwargs()
        kwargs.update({'initial': {'cajero': self.request.user.id,
                                   'cliente': self.examen.persona.id,
                                   'remite': self.examen.remitio}})
        return kwargs

    def dispatch(self, *args, **kwargs):
        """Obtiene el :class:`Recibo` que se entrego como argumento en la
        url"""

        self.examen = get_object_or_404(Examen, pk=kwargs['examen'])
        return super(ReciboExamenCreateView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReciboExamenCreateView, self).get_context_data(**kwargs)
        context['persona'] = self.examen.persona
        return context

    def form_valid(self, form):
        self.object = form.save()

        venta = Venta()
        venta.item = self.examen.tipo_de_examen.item
        venta.recibo = self.object
        venta.cantidad = 1
        venta.precio = venta.item.precio_de_venta
        venta.impuesto = venta.item.impuestos

        venta.save()
        self.object.ventas.add(venta)
        self.examen.facturado = True
        self.examen.save()

        self.object.save()

        return HttpResponseRedirect(self.object.get_absolute_url())


class VentaDeleteView(DeleteView, LoginRequiredMixin):
    """Permite eliminar una :class:`Venta` que sea incorrecta en el
    :class:`Recibo`"""
    model = Venta

    def get_object(self, queryset=None):
        obj = super(VentaDeleteView, self).get_object(queryset)
        self.recibo = obj.recibo
        return obj

    def get_success_url(self):
        return self.recibo.get_absolute_url()


class ReciboFormMixin(CreateView):
    """Especifica una interfaz común para la creación de Entidades que requieran
    un :class:`Recibo` como parte de los campos requeridos por su formulario"""

    def dispatch(self, *args, **kwargs):
        self.recibo = get_object_or_404(Recibo, pk=kwargs['recibo'])
        return super(ReciboFormMixin, self).dispatch(*args, **kwargs)

    def get_initial(self):
        initial = super(ReciboFormMixin, self).get_initial()
        initial = initial.copy()
        initial['recibo'] = self.recibo.id
        return initial


class VentaCreateView(ReciboFormMixin, LoginRequiredMixin):
    """Permite agregar :class:`Venta`s a un :class:`Recibo`"""

    model = Venta
    form_class = VentaForm

    def form_valid(self, form):
        """Guarda el objeto generado espeficando precio obtenido directamente
        del :class:`Producto`"""

        self.object = form.save(commit=False)
        if self.object.precio == Decimal(0):
            self.object.precio = self.object.item.precio_de_venta
        self.object.impuesto = self.object.item.impuestos * self.object.monto()
        self.object.save()

        # messages.info(self.request, u"Agregada una Venta al Recibo!")

        return HttpResponseRedirect(self.get_success_url())


class ReciboDetailView(DetailView, LoginRequiredMixin):
    """Muestra los detalles del :class:`Recibo` para agregar :class:`Producto`s
    ir a la vista de impresión y realizar otras tareas relacionadas con
    facturación"""

    model = Recibo
    object_context_name = 'recibo'
    template_name = 'invoice/recibo_detail.html'

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Venta` para agregar
        :class:`Producto`s"""

        context = super(ReciboDetailView, self).get_context_data(**kwargs)
        context['form'] = VentaForm(initial={'recibo': context['recibo'].id})
        context['form'].helper.form_action = reverse('venta-add', args=[
            context['recibo'].id])

        context['pago_form'] = PagoForm(
            initial={'recibo': context['recibo'].id})
        context['pago_form'].helper.form_action = reverse('pago-add', args=[
            context['recibo'].id])

        return context


class ReciboAnularView(RedirectView, LoginRequiredMixin):
    """Marca un :class:`Recibo` como anulado para que la facturación del mismo
    no se vea reflejado en los cortes de caja"""

    permanent = False

    def get_redirect_url(self, **kwargs):
        recibo = get_object_or_404(Recibo, pk=kwargs['pk'])
        recibo.anular()
        messages.info(self.request, u'¡El recibo ha sido marcado como anulado!')
        return reverse('invoice-view-id', args=[recibo.id])


class ReciboCerrarView(RedirectView, LoginRequiredMixin):
    """Marca un :class:`Recibo` como anulado para que la facturación del mismo
    no se vea reflejado en los cortes de caja"""

    permanent = False

    def get_redirect_url(self, **kwargs):
        recibo = get_object_or_404(Recibo, pk=kwargs['pk'])
        recibo.cerrar()
        messages.info(self.request, u'¡El recibo ha sido cerrado!')
        return reverse('invoice-view-id', args=[recibo.id])


class ReciboPeriodoView(TemplateView):
    """Obtiene los :class:`Recibo` de un periodo determinado en base
    a un formulario que las clases derivadas deben proporcionar como
    self.form"""

    def dispatch(self, request, *args, **kwargs):
        """Efectua la consulta de los :class:`Recibo` de acuerdo a los
        datos ingresados en el formulario"""

        if self.form.is_valid():
            self.inicio = self.form.cleaned_data['inicio']
            self.fin = self.form.cleaned_data['fin']
            self.recibos = Recibo.objects.filter(
                created__gte=self.inicio,
                created__lte=self.fin,
            )

        return super(ReciboPeriodoView, self).dispatch(request, *args, **kwargs)


class ReporteReciboView(ReciboPeriodoView, LoginRequiredMixin):
    """Muestra los ingresos captados mediante :class:`Recibo`s que se captaron
    durante el periodo especificado"""

    template_name = 'invoice/recibo_list.html'

    def dispatch(self, request, *args, **kwargs):
        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='recibo')

        return super(ReporteReciboView, self).dispatch(request, *args,
                                                       **kwargs)

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReporteReciboView, self).get_context_data(**kwargs)

        context['recibos'] = self.recibos
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        context['total'] = sum(r.total() for r in self.recibos.all())

        return context


class ReporteReciboDetailView(ReciboPeriodoView):
    """Muestra los ingresos captados mediante :class:`Recibo`s que se captaron
    durante el periodo especificado"""

    template_name = 'invoice/recibo_detail_list.html'

    def dispatch(self, request, *args, **kwargs):
        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='recibodetail')

        return super(ReporteReciboDetailView, self).dispatch(request, *args,
                                                             **kwargs)

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReporteReciboDetailView, self).get_context_data(
            **kwargs)

        context['recibos'] = self.recibos
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        context['total'] = sum(r.total() for r in self.recibos.all())

        return context


class ReporteTipoView(ReciboPeriodoView):
    """Muestra los ingresos captados mediante :class:`Recibo`s que se captaron
    durante el periodo especificado"""

    template_name = 'invoice/tipo_list.html'

    def dispatch(self, request, *args, **kwargs):

        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='tipo')

        return super(ReporteTipoView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):

        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReporteTipoView, self).get_context_data(**kwargs)

        context['cantidad'] = 0
        context['total'] = Decimal('0')
        categorias = defaultdict(lambda: defaultdict(Decimal))
        self.recibos = self.recibos.filter(nulo=False)
        for recibo in self.recibos.all():

            for venta in recibo.ventas.all():
                monto = venta.total()
                categoria = venta.item.item_type.first()

                categorias[categoria]['monto'] += monto
                categorias[categoria]['cantidad'] += 1

                context['cantidad'] += 1
                context['total'] += monto

        context['recibos'] = self.recibos
        context['categorias'] = categorias.items()
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        return context


class ReporteProductoView(ReciboPeriodoView, LoginRequiredMixin):
    """Muestra los ingresos captados mediante :class:`Recibo`s, distribuyendo
    los mismos de acuerdo al :class:`Producto` que se facturó, tomando en
    cuenta el periodo especificado"""

    template_name = 'invoice/producto_list.html'

    def dispatch(self, request, *args, **kwargs):

        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='producto')

        return super(ReporteProductoView, self).dispatch(request, *args,
                                                         **kwargs)

    def get_context_data(self, **kwargs):

        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReporteProductoView, self).get_context_data(**kwargs)

        context['cantidad'] = 0
        context['total'] = Decimal('0')
        productos = defaultdict(lambda: defaultdict(Decimal))

        for recibo in self.recibos.all():

            for venta in recibo.ventas.all():
                productos[venta.item]['monto'] += venta.monto()
                productos[venta.item]['cantidad'] += 1

                context['cantidad'] += 1

        context['recibos'] = self.recibos
        context['productos'] = productos.items()
        context['impuesto'] = sum(r.impuesto() for r in self.recibos.all())
        context['total'] = sum(r.total() for r in self.recibos.all())
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        return context


class VentaListView(ListView):
    context_object_name = 'ventas'

    def dispatch(self, request, *args, **kwargs):
        self.form = VentaPeriodoForm(request.GET, prefix='venta')
        if self.form.is_valid():
            self.inicio = self.form.cleaned_data['inicio']
            self.fin = datetime.combine(self.form.cleaned_data['fin'], time.max)
            self.item = self.form.cleaned_data['item']

        return super(VentaListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Venta.objects.filter(
            recibo__created__gte=self.inicio,
            recibo__created__lte=self.fin,
            recibo__nulo=False,
            item=self.item,
        )

    def get_context_data(self, **kwargs):
        context = super(VentaListView, self).get_context_data(**kwargs)
        context['item'] = self.item
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        context['total'] = sum(v.total() for v in self.object_list)
        return context


class ReciboRemiteView(ReciboPeriodoView, LoginRequiredMixin):
    """Muestra los ingresos captados mediante :class:`Recibo`s, distribuyendo
    los mismos de acuerdo al :class:`Producto` que se facturó, tomando en
    cuenta el periodo especificado"""

    template_name = 'invoice/remite_list.html'

    def dispatch(self, request, *args, **kwargs):
        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='remite')

        return super(ReciboRemiteView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReciboRemiteView, self).get_context_data(**kwargs)

        context['cantidad'] = Decimal('0')
        doctores = defaultdict(lambda: defaultdict(Decimal))

        for recibo in self.recibos.all():
            doctores[recibo.remite.upper()]['monto'] += recibo.total()
            doctores[recibo.remite.upper()]['cantidad'] += 1
            doctores[recibo.remite.upper()][
                'comision'] += recibo.comision_doctor()

        context['cantidad'] = sum(doctores[d]['comision'] for d in doctores)

        context['recibos'] = self.recibos
        context['inicio'] = self.inicio
        context['doctores'] = doctores.items()
        context['fin'] = self.fin
        return context


class ReciboRadView(ReciboPeriodoView, LoginRequiredMixin):
    """Legacy - Muestra los honorarios médicos de los radiologos

    Obsoleto
    """

    template_name = 'invoice/radiologo_list.html'

    def dispatch(self, request, *args, **kwargs):
        """Agrega el formulario"""

        self.form = PeriodoForm(request.GET, prefix='rad')

        return super(ReciboRadView, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Agrega el formulario de :class:`Recibo`"""

        context = super(ReciboRadView, self).get_context_data(**kwargs)

        context['cantidad'] = Decimal('0')
        doctores = defaultdict(lambda: defaultdict(Decimal))

        for recibo in self.recibos.all():
            radiologo = recibo.radiologo.upper()

            if not radiologo in doctores:
                doctores[radiologo]['recibos'] = list()

            doctores[radiologo]['recibos'].append(recibo)
            doctores[radiologo]['monto'] += recibo.total()
            doctores[radiologo]['cantidad'] += 1
            doctores[radiologo]['comision'] += recibo.comision_radiologo()

        context['cantidad'] = sum(doctores[d]['comision'] for d in doctores)
        context['costo'] = sum(r.total() for r in self.recibos.all())

        context['recibos'] = self.recibos
        context['inicio'] = self.inicio
        context['doctores'] = doctores.items()
        context['fin'] = self.fin
        return context


class EmergenciaPeriodoView(TemplateView, LoginRequiredMixin):
    """Muestra las opciones disponibles para la aplicación"""

    template_name = 'invoice/emergencia_list.html'

    def dispatch(self, request, *args, **kwargs):

        """Filtra las :class:`Emergencia` de acuerdo a los datos ingresados en
        el formulario"""

        self.form = PeriodoForm(request.GET, prefix='emergencia')
        if self.form.is_valid():

            self.inicio = self.form.cleaned_data['inicio']
            self.fin = datetime.combine(self.form.cleaned_data['fin'], time.max)
            self.emergencias = Emergencia.objects.filter(
                created__gte=self.inicio,
                created__lte=self.fin
            )

        else:

            return redirect('invoice-index')

        return super(EmergenciaPeriodoView, self).dispatch(request, *args,
                                                           **kwargs)

    def get_context_data(self, **kwargs):

        """Permite utilizar las :class:`Emergencia`s en la vista"""

        context = super(EmergenciaPeriodoView, self).get_context_data(**kwargs)
        context['emergencias'] = self.emergencias
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        return context


class EmergenciaDiaView(ListView, LoginRequiredMixin):
    """Muestra los materiales y medicamentos de las :class:`Emergencia`s que
    han sido atendidas durante el día"""

    context_object_name = 'emergencias'
    template_name = 'invoice/emergency.html'
    paginate_by = 10

    def get_queryset(self):
        return Emergencia.objects.filter(facturada=False)


class ExamenView(ListView, LoginRequiredMixin):
    """Muestra los materiales y medicamentos de las :class:`Emergencia`s que
    han sido atendidas durante el día"""

    context_object_name = 'examenes'
    template_name = 'invoice/examen_list.html'
    paginate_by = 10

    def get_queryset(self):
        return Examen.objects.filter(facturado=False)


def crear_ventas(items, recibo, examen=False, tecnico=False):
    """Permite convertir un :class:`dict` de :class:`ItemTemplate` y sus
    cantidades en una las :class:`Venta`s de un :class:`Recibo`

    Toma en consideración las indicaciones acerca de los cobros de comisiones
    indicados por los examenes"""

    for item in items:
        venta = Venta()
        venta.item = item
        venta.recibo = recibo
        venta.cantidad = items[item]

        precio = item.precio_de_venta

        if examen:
            comisiones = precio * item.comision * dot01
            if tecnico:
                comisiones += precio * item.comision2 * dot01
            venta.precio = precio - comisiones
        else:
            venta.precio = precio
        venta.impuesto = item.impuestos

        venta.save()
        recibo.ventas.add(venta)


class EmergenciaFacturarView(UpdateView, LoginRequiredMixin):
    """Permite crear de manera automática un :class:`Recibo` con todas sus
    :class:`Ventas` a partir de una :class:`Emergencia` que aun no se haya
    marcado como facturada"""

    model = Emergencia
    form_class = EmergenciaFacturarForm
    context_object_name = 'emergencia'
    template_name = 'invoice/emergency_form.html'

    @method_decorator(permission_required('invoice.cajero'))
    def dispatch(self, *args, **kwargs):
        return super(EmergenciaFacturarView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)

        items = self.object.facturar()

        recibo = Recibo()
        recibo.cajero = self.request.user
        recibo.cliente = self.object.persona
        recibo.tipo_de_venta = self.object.tipo_de_venta

        recibo.save()

        crear_ventas(items, recibo)

        self.object.facturado = True
        self.object.save()

        return HttpResponseRedirect(recibo.get_absolute_url())


class AdmisionFacturarView(UpdateView, LoginRequiredMixin):
    """Permite crear de manera automática un :class:`Recibo` con todas sus
    :class:`Ventas` a partir de una :class:`Admision` que aun no se haya marcado
    como facturada"""

    model = Admision
    context_object_name = 'admision'
    form_class = AdmisionFacturarForm
    template_name = 'invoice/admision_form.html'

    @method_decorator(permission_required('invoice.cajero'))
    def dispatch(self, *args, **kwargs):
        return super(AdmisionFacturarView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)

        items = self.object.facturar()

        recibo = Recibo()
        recibo.cajero = self.request.user
        recibo.cliente = self.object.paciente
        recibo.tipo_de_venta = self.object.tipo_de_venta

        recibo.save()

        crear_ventas(items, recibo)

        for honorario in self.object.honorarios.all():
            venta = Venta()
            venta.item = honorario.item
            venta.recibo = recibo
            venta.cantidad = 1
            venta.precio = honorario.monto
            venta.impuesto = honorario.item.impuestos
            venta.descontable = False

            venta.save()
            recibo.ventas.add(venta)

        for deposito in self.object.depositos.all():
            pago = Pago()
            pago.recibo = recibo
            pago.monto = deposito.monto
            pago.tipo = TipoPago.objects.get(pk=config.DEPOSIT_PAYMENT)
            pago.save()

        self.object.ultimo_cobro = timezone.now()
        self.object.save()

        return HttpResponseRedirect(recibo.get_absolute_url())


class ExamenFacturarView(UpdateView, LoginRequiredMixin):
    """Permite crear de manera automática un :class:`Recibo` con todas sus
    :class:`Ventas` a partir de una :class:`Admision` que aun no se haya marcado
    como facturada"""

    model = Examen
    context_object_name = 'examen'
    form_class = ExamenFacturarForm
    template_name = 'invoice/examen_form.html'

    @method_decorator(permission_required('invoice.cajero'))
    def dispatch(self, *args, **kwargs):
        return super(ExamenFacturarView, self).dispatch(*args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)

        items = self.object.facturar()

        recibo = Recibo()
        recibo.cajero = self.request.user
        recibo.cliente = self.object.persona
        recibo.radiologo = self.object.radiologo
        recibo.tipo_de_venta = self.object.tipo_de_venta
        recibo.save()

        # Crear los honorarios de los radiologos
        honorarios = sum(i.precio_de_venta * i.comision * dot01 for i in items)
        venta = Venta()
        venta.recibo = recibo
        venta.precio = honorarios
        venta.cantidad = 1
        venta.item = self.object.radiologo.item
        venta.impuesto = self.object.radiologo.item.impuestos
        venta.save()

        venta_tecnico = False
        if not self.object.tecnico is None:
            # Crear los honorarios de los tecnicos
            tecnico = sum(
                i.precio_de_venta * i.comision2 * dot01 for i in items)
            venta = Venta()
            venta.recibo = recibo
            venta.precio = tecnico
            venta.cantidad = 1
            venta.item = self.object.tecnico.item
            venta.impuesto = self.object.tecnico.item.impuestos
            venta.save()
            venta_tecnico = True

        crear_ventas(items, recibo, True, venta_tecnico)

        self.object.save()

        return HttpResponseRedirect(recibo.get_absolute_url())


class AdmisionAltaView(ListView, LoginRequiredMixin):
    """Muestra una lista de :class:`Admisiones` que aun no han sido facturadas"""

    context_object_name = 'admisiones'
    template_name = 'invoice/admisiones.html'
    paginate_by = 10

    def get_queryset(self):
        """Obtiene las :class:`Admision`es que aun no han sido facturadas"""

        return Admision.objects.filter(facturada=False)


class CorteView(ReciboPeriodoView):
    template_name = 'invoice/corte.html'

    def get_context_data(self, **kwargs):
        context = super(CorteView, self).get_context_data(**kwargs)
        context['cajero'] = self.form.cleaned_data['usuario']
        context['recibos'] = self.recibos.filter(cajero=context['cajero'])
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        context['total'] = sum(r.total() for r in context['recibos'].all())
        return context

    def dispatch(self, request, *args, **kwargs):
        self.form = CorteForm(request.GET, prefix='corte')
        return super(CorteView, self).dispatch(request, *args, **kwargs)


class ReciboInventarioView(ReciboPeriodoView, LoginRequiredMixin):
    template_name = 'invoice/recibo_inventario_list.html'

    def dispatch(self, request, *args, **kwargs):
        """Agrega el formulario"""

        self.form = InventarioForm(request.GET, prefix='inventario')

        return super(ReciboInventarioView, self).dispatch(request, *args,
                                                          **kwargs)

    def get_context_data(self, **kwargs):

        context = super(ReciboInventarioView, self).get_context_data(**kwargs)

        items = defaultdict(lambda: defaultdict(int))

        ventas = Venta.objects.filter(recibo__created__gte=self.inicio,
                                      recibo__created__lte=self.fin)

        for venta in ventas.all():
            items[venta.item]['cantidad'] += venta.cantidad

        queryset = ItemTemplate.objects.annotate(
            total=models.Sum('items__cantidad'))

        for item in queryset.all():

            if item in items:
                items[item]['inventario'] = item.total

        context['inicio'] = self.inicio
        context['items'] = items.items()
        context['fin'] = self.fin
        return context


class PagoCreateView(ReciboFormMixin, LoginRequiredMixin):
    """Permite agregar una forma de :class:`Pago` a un :class:`Recibo`"""
    model = Pago
    form_class = PagoForm


class TurnoCajaDetailView(DetailView, LoginRequiredMixin):
    model = TurnoCaja
    context_object_name = "turno"


class TurnoCajaCreateView(CreateView, CurrentUserFormMixin):
    model = TurnoCaja
    form_class = TurnoCajaForm


class TurnoCajaUpdateView(UpdateView, LoginRequiredMixin):
    model = TurnoCaja
    form_class = TurnoCajaForm


class TurnoCajaFormMixin(CreateView, LoginRequiredMixin):
    def dispatch(self, *args, **kwargs):
        self.turno = get_object_or_404(TurnoCaja, pk=kwargs['turno'])
        return super(TurnoCajaFormMixin, self).dispatch(*args, **kwargs)

    def get_initial(self):
        initial = super(TurnoCajaFormMixin, self).get_initial()
        initial = initial.copy()
        initial['turno'] = self.turno.id
        return initial


class CierreTurnoCreateView(TurnoCajaFormMixin):
    model = CierreTurno
    form_class = CierreTurnoForm


class TurnoCajaUpdateView(UpdateView, LoginRequiredMixin):
    model = TurnoCaja
    form_class = TurnoCajaCierreForm


class DepositoDetailView(DetailView, LoginRequiredMixin):
    model = Deposito
    context_object_name = 'deposito'


class DepositoFacturarView(UpdateView, LoginRequiredMixin):
    model = Deposito
    form_class = DepositoForm

    def form_valid(self, form):
        self.object = form.save(commit=False)

        recibo = Recibo()
        recibo.cajero = self.request.user
        recibo.cliente = self.object.admision.paciente
        recibo.save()

        venta = Venta()
        venta.item = ItemTemplate.objects.get(pk=config.DEPOSIT_ACCOUNT)
        venta.recibo = recibo
        venta.cantidad = 1
        venta.precio = self.object.monto
        venta.impuesto = 0
        venta.descontable = False
        venta.save()

        return HttpResponseRedirect(recibo.get_absolute_url())


class VentaAreaListView(ListView):
    context_object_name = 'ventas'

    def dispatch(self, request, *args, **kwargs):
        self.form = PeriodoAreaForm(request.GET, prefix='venta-area')
        if self.form.is_valid():
            self.inicio = self.form.cleaned_data['inicio']
            self.fin = self.form.cleaned_data['fin']
            self.item_type = self.form.cleaned_data['area']

        return super(VentaAreaListView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return Venta.objects.filter(
            recibo__created__gte=self.inicio,
            recibo__created__lte=self.fin,
            recibo__nulo=False,
            item__item_type=self.item_type,
        )

    def get_context_data(self, **kwargs):
        context = super(VentaAreaListView, self).get_context_data(**kwargs)
        context['item_type'] = self.item_type
        context['inicio'] = self.inicio
        context['fin'] = self.fin
        context['total'] = sum(v.total() for v in self.object_list)
        return context
