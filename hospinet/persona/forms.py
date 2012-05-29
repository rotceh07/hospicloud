# -*- coding: utf-8 -*-
from persona.models import (Persona, Fisico, EstiloVida, Antecedente,
    AntecedenteFamiliar, AntecedenteObstetrico, AntecedenteQuirurgico)
from django import forms

class PersonaForm(forms.ModelForm):
    
    """Permite mostrar una interfaz para capturar los datos de una
    :class:`Persona`"""
    
    class Meta:
        
        model = Persona
    
    nacimiento = forms.DateTimeField(widget=forms.DateInput(
                    attrs={'class': 'datepicker' }, format='%d/%m/%Y'),
                 input_formats=('%d/%m/%Y',))
    
    def clean(self):
        
        """Realiza la validación de la identidad que fue ingresada luego de
        limpiar los datos de modo que sean seguros para la base de datos"""
        
        super(PersonaForm, self).clean()
        cleaned_data = self.cleaned_data
        tipo_identidad = cleaned_data.get('tipo_identificacion')
        iden = cleaned_data.get('identificacion')
        if tipo_identidad == 'T' and not Persona.validar_identidad(iden):
            raise forms.ValidationError('La identidad ingresada no es valida')
        
        return cleaned_data

class FisicoForm(forms.ModelForm):
    
    class Meta:
        
        model = Fisico
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())

class EstiloVidaForm(forms.ModelForm):
    
    class Meta:
        
        model = EstiloVida
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())

class AntecedenteForm(forms.ModelForm):
    
    class Meta:
        
        model = Antecedente
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())

class AntecedenteFamiliarForm(forms.ModelForm):
    
    class Meta:
        
        model = AntecedenteFamiliar
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())

class AntecedenteObstetricoForm(forms.ModelForm):
    
    class Meta:
        
        model = AntecedenteObstetrico
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())

class AntecedenteQuirurgicoForm(forms.ModelForm):
    
    class Meta:
        
        model = AntecedenteQuirurgico
    
    persona = forms.ModelChoiceField(label="",
                                  queryset=Persona.objects.all(),
                                  widget=forms.HiddenInput())