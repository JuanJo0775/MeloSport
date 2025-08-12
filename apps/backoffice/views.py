from django.shortcuts import render

def dashboard(request):
    return render(request, "backoffice/dashboard.html")

def login_view(request):
    return render(request, "backoffice/login.html")
