from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.conf import settings
import os
import yt_dlp
import assemblyai as aai
import requests
from .models import BlogPost

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

def yt_title(link):
    try:
        ydl_opts = {
            'quiet': True,  # Suppress unnecessary output
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=False)
            title = info_dict.get('title', 'Title not available')
            return title
    except Exception as e:
        print(f"Error fetching title with yt-dlp: {e}")
        return "Error fetching title"

def download_audio(link):
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            audio_file = ydl.prepare_filename(info_dict)
            audio_file = os.path.splitext(audio_file)[0] + '.mp3'
            return audio_file
    except Exception as e:
        print(f"Error downloading audio with yt-dlp: {e}")
        return None

def get_transcription(link):
    audio_file = download_audio(link)
    if not audio_file:
        return None
    
    aai.settings.api_key = '6968f259c784459593490100d584c2b2'

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text if transcript else None



def generate_blog_from_transcription(transcription):
    # OpenRouter API endpoint
    API_URL = "https://openrouter.ai/api/v1/chat/completions"
    API_KEY = "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"  # Replace with your OpenRouter API key

    # Define the blog prompt
    prompt = (
        "Based on the following transcript from a YouTube video, "
        "write a comprehensive blog article. Make it look like a proper blog article, "
        "not a transcript of a video:\n\n"
        f"{transcription}\n\nBlog Article:"
    )

    # Payload for the API request
    payload = {
        "model": "openai/gpt-3.5-turbo",  # Use other models available on OpenRouter
        "messages": [
            {"role": "system", "content": "You are a helpful and creative blog writer."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.7
    }

    # Headers for the request
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # Send a POST request to OpenRouter
        response = requests.post(API_URL, headers=headers, json=payload)

        # Check if the request was successful
        if response.status_code == 200:
            generated_content = response.json()['choices'][0]['message']['content'].strip()
            return generated_content
        else:
            print(f"Error {response.status_code}: {response.text}")
            return None

    except Exception as e:
        print(f"Error generating blog: {e}")
        return None
@csrf_exempt
def generate_blog(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)
        
        # Get YouTube title
        title = yt_title(yt_link)

        # Get transcript
        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({'error': "Failed to get transcript"}, status=500)
        
        # Generate blog content
        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse({'error': "Failed to generate blog article"}, status=500)
        
        #save article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()
        
        return JsonResponse({'content': blog_content})
    

    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all_blogs_list.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog_details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == "POST":
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword and password != "":
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message': error_message})
            
        elif password == "":
            error_message = 'Password cannot be empty'
            return render(request, 'signup.html', {'error_message': error_message})

        else:            
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})
    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')
