from django.shortcuts import render

def index(request):
    return render(request, 'index.html')
    
def deconstructor(request):
    return render(request, 'deconstructor.html')

def constructor(request):
    return render(request, 'constructor.html')

def interactive_map(request):
    return render(request, 'interactive_map.html')

def demonstrator(request):
    return render(request, 'demonstrator.html')