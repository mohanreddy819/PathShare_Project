from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
import requests
import polyline
import geopy.distance
import googlemaps
import math
from .models import *
from django.http import HttpResponse, JsonResponse,HttpResponseForbidden
from django.contrib.auth.models import User
from django.contrib import messages



def index(request):
    return render(request, 'index.html')
#######################################################################################################
# def chatroom(request):
#     if request.method == 'POST':
#         # Get the input data from the form
#         source = request.POST.get('source')
#         destination = request.POST.get('destination')
#         day_of_journey = request.POST.get('day_of_journey')
#         time_of_journey = request.POST.get('time_of_journey')
#         user_telegram_number = request.POST.get('user_telegram_number')

#         # Check if the group already exists based on source, destination, and time
#         group = Group.objects.filter(
#             source=source, 
#             destination=destination, 
#             day_of_journey=day_of_journey, 
#             time_of_journey=time_of_journey
#         ).first()

#         # If the group exists and has space, add the user to the group
#         if group and group.member_count < 5:
#             user = User.objects.get(username=request.user.username)
#             # Add the user to the group (you can add a Many-to-Many relationship if necessary)
#             group.member_count += 1
#             group.save()
#             messages.success(request, 'You have joined the group!')
#             return redirect('chatroom', group_id=group.id)

#         # If the group doesn't exist, create a new one
#         elif not group:
#             group = Group.objects.create(
#                 source=source,
#                 destination=destination,
#                 day_of_journey=day_of_journey,
#                 time_of_journey=time_of_journey,
#                 member_count=1  # The user is the first member
#             )
#             messages.success(request, 'New group created and you are added to it!')
#             return redirect('chatroom', group_id=group.id)

#         # If the group is full
#         else:
#             messages.error(request, 'This group is full! You cannot join.')
#             return redirect('chatroom')

#     else:
#         # GET request: Display existing groups and their messages
#         groups = Group.objects.all()  # You can filter based on the user's available groups
#         return render(request, 'chatroom.html', {'groups': groups})
#############################################################################################################
# def previous_rides(request):
#     return render(request, 'PreviousRides.html')

from django.shortcuts import render, redirect
from .models import Customer

def profile(request):
    customer_id = request.session.get('customer_id')

    if not customer_id:
        return redirect('login')
    try:
        customer = Customer.objects.get(customer_id=customer_id)
    except Customer.DoesNotExist:
        request.session.flush()
        return redirect('login')

    return render(request, 'profile.html', {
        'customer': customer
    })


def home(request):
    return render(request, 'home.html')


def registration(request):
    if request.method == 'POST':
        name = request.POST.get('reg-name')
        email = request.POST.get('reg-email')
        number = request.POST.get('reg-phone')
        gender = request.POST.get('reg-gender')
        pic = request.POST.get('reg-pic')
        password = request.POST.get('reg-password')

        customer = Customer(
                customer_name=name,
                email=email,
                phone_number=number,
                gender=gender,
                profile_pic=pic,
                password=password
            )
        customer.save()
            
    return render(request, 'index.html', {})

def login(request):
    if request.method == "POST":
        name = request.POST.get('name')
        password = request.POST.get('password')

        try:
            customer = Customer.objects.get(customer_name=name)

            if customer.password == password:
                request.session['customer_id'] = customer.customer_id
                request.session['customer_name'] = customer.customer_name
                print("Session ID after login:", request.session.get('customer_id'))  # Debugging session data
                return render(request, 'home.html', {'customer_name': customer.customer_name})
            else:
                return render(request, 'index.html', {'alert_message': 'Incorrect Password!'})
        except Customer.DoesNotExist:
            return render(request, 'index.html', {'alert_message': 'User does not exist!'})

    return render(request, 'index.html', {})


def logout(request):
    request.session.flush() 
    return redirect('login') 

def get_coordinates(location, api_key):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": api_key}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['results']:
            coordinates = data['results'][0]['geometry']['location']
            return (coordinates['lat'], coordinates['lng'])
    return None

def get_route_polyline(start_location, end_location, api_key):
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {"origin": start_location, "destination": end_location, "key": api_key}
    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if 'routes' in data and len(data['routes']) > 0:
            polyline_encoded = data['routes'][0]['overview_polyline']['points']
            return polyline.decode(polyline_encoded)
    return None

def is_point_on_route(start_location, end_location, point_location1, point_location2, api_key):
    start_coords = get_coordinates(start_location, api_key)
    end_coords = get_coordinates(end_location, api_key)
    point_coords1 = get_coordinates(point_location1, api_key)
    point_coords2 = get_coordinates(point_location2, api_key)

    if not start_coords or not end_coords or not point_coords1 or not point_coords2:
        return False
    polyline_points = get_route_polyline(start_location, end_location, api_key)
    if polyline_points is None:
        return False

    threshold = 500
    for i in range(len(polyline_points) - 1):
        segment_start = polyline_points[i]
        segment_end = polyline_points[i + 1]

        if (is_point_near_segment(segment_start, segment_end, point_coords1, threshold) or
            is_point_near_segment(segment_start, segment_end, point_coords2, threshold)):
            return True

    return False

def is_point_near_segment(segment_start, segment_end, point, threshold):
    start_lat, start_lon = segment_start
    end_lat, end_lon = segment_end
    point_lat, point_lon = point

    start_lat, start_lon = map(math.radians, [start_lat, start_lon])
    end_lat, end_lon = map(math.radians, [end_lat, end_lon])
    point_lat, point_lon = map(math.radians, [point_lat, point_lon])

    segment_vector_x = end_lon - start_lon
    segment_vector_y = end_lat - start_lat
    point_vector_x = point_lon - start_lon
    point_vector_y = point_lat - start_lat

    cross_product = point_vector_x * segment_vector_y - point_vector_y * segment_vector_x
    segment_length = geopy.distance.great_circle(segment_start, segment_end).meters
    distance_to_segment = abs(cross_product) / segment_length

    return distance_to_segment < threshold


def create_ride(request):
    api_key = 'AIzaSyAHYezyDH5fTt69pSukaWV7bnUz1IV3iro'
    gmaps = googlemaps.Client(key=api_key)

    if request.method == "POST":
        female_only = request.POST.get("female_only") == 'true'
        source = request.POST.get("start_location")
        destination = request.POST.get("end_location")
        shared = 'shared' in request.POST

        # Get the route information from Google Maps API
        directions = gmaps.directions(source, destination, mode="driving", units="metric")
        distance = directions[0]['legs'][0]['distance']['value'] / 1000  # Convert from meters to kilometers
        cost = math.ceil(distance * 25)  # Example cost calculation based on distance
    
        customer_id = request.session.get('customer_id')
        if not customer_id:
            return redirect('login')  # Ensure user is logged in

        # If shared and female-only, ensure the gender is correct
        if shared and female_only and request.session.get('Gender') != 'F':
            return redirect('home')

        elif shared:
            # Check for an existing shared ride that fits the criteria
            rides = all_rides.objects.all()
            for ride in rides:
                if is_point_on_route(ride.start, ride.end, source, destination, api_key) and \
                   ((female_only and ride.female_only) or (not female_only and not ride.female_only)) and \
                   ride.passenger_count < 4:  # Ensure ride has available space
                    # Add the new passenger to the ride using customer_id
                    ride.passengers[customer_id] = {
                        "Source": source.split(",")[0],
                        "Destination": destination.split(",")[0],
                        "Distance": distance,
                        "Cost": 0  # Cost for this passenger
                    }
                    ride.passenger_count += 1
                    ride.save()

                    # Add the ride to the customer's previous rides using the Ride model
                    customer = Customer.objects.get(customer_id=customer_id)
                    passenger_data = ride.passengers[customer_id]

                    # Create a new Ride record for the customer and save it
                    ride_instance = Ride(
                        customer=customer,
                        start_location=passenger_data['Source'],
                        end_location=passenger_data['Destination'],
                        distance=passenger_data['Distance'],
                        cost=passenger_data['Cost'],
                        female_only=female_only,
                        shared=shared
                    )
                    ride_instance.save()  # Save the ride record to the database

                    return redirect('previous_rides')

            # If no shared ride was found, create a new ride
            ridetemp = all_rides(
                female_only=female_only,
                start=source,
                end=destination,
                shared=shared,
                total_distance=distance,
                total_cost=cost,
                passenger_count=1,
                passengers={
                    customer_id: {
                        "Source": source.split(",")[0],
                        "Destination": destination.split(",")[0],
                        "Distance": distance,
                        "Cost": 0
                    }
                }
            )
            ridetemp.save()

        else:
            # If it's not a shared ride, just create a single-passenger ride
            ridetemp = all_rides(
                female_only=female_only,
                start=source,
                end=destination,
                shared=shared,
                total_distance=distance,
                total_cost=cost,
                passenger_count=1,
                passengers={
                    customer_id: {
                        "Source": source.split(",")[0],
                        "Destination": destination.split(",")[0],
                        "Distance": distance,
                        "Cost": 0
                    }
                }
            )
            ridetemp.save()

        # Add the new ride to the customer's previous rides using the Ride model
        customer = Customer.objects.get(customer_id=customer_id)
        passenger_data = ridetemp.passengers[customer_id]

        # Create a new Ride record for the customer and save it
        ride_instance = Ride(
            customer=customer,
            start_location=passenger_data['Source'],
            end_location=passenger_data['Destination'],
            distance=passenger_data['Distance'],
            cost=passenger_data['Cost'],
            female_only=female_only,
            shared=shared
        )
        ride_instance.save()  # Save the ride record to the database

    return redirect('previous_rides')


def calculate_fare(request):
    rides = all_rides.objects.all()
    for ride in rides:
        adaptive_fare_splitting(ride)
    return redirect('previous_rides') 

def adaptive_fare_splitting(ride):
    total_distance = sum(
        passenger_details["Distance"]
        for passenger_key, passenger_details in ride.passengers.items()
    )

    for passenger_key, passenger_details in ride.passengers.items():
        passenger_distance = passenger_details["Distance"]
        proportional_cost = math.ceil((passenger_distance / total_distance) * ride.total_cost)
        passenger_details["Cost"] = proportional_cost

    ride.save()

def previous_rides(request):
    customer_id = request.session.get('customer_id')
    if not customer_id:
        return redirect('login')

    all_rides_for_user = all_rides.objects.all()

    for ride in all_rides_for_user:
        # Check if the customer_id exists as a key in the passengers field
        if customer_id in ride.passengers:
            passenger_data = ride.passengers[customer_id]
            current_ride_details = {
                "source": passenger_data["Source"],
                "destination": passenger_data["Destination"],
                "distance": passenger_data["Distance"],
                "cost": passenger_data["Cost"]
            }
            break
    previous_rides = Ride.objects.filter(customer__customer_id=customer_id)
    context = {
        'current_ride': current_ride_details,
        'previous_rides': previous_rides,
    }
    return render(request, 'PreviousRides.html', context)


#### group creation
@login_required
# def create_group(request):
#     # Fetch all groups
#     groups = Group.objects.all()
#     if request.method == "POST":
#         # Fetch form data
#         source = request.POST.get('source')
#         destination = request.POST.get('destination')
#         day_of_journey = request.POST.get('day_of_journey')
#         time_of_journey = request.POST.get('time_of_journey')
#         female_only = request.POST.get('female_only') == "on"
        
#         # Check if there's a logged-in customer, if not, use a fallback user
#         try:
#             customer = Customer.objects.get(email=request.user.email)
#         except Customer.DoesNotExist:
#             # If no customer is found, use a placeholder (e.g., admin user)
#             customer = Customer.objects.first()  # Or any other fallback method

#         # Check if there's an existing group for the given details
#         existing_group = Group.objects.filter(
#             source=source, destination=destination, female_only=female_only, member_count__lt=4
#         ).first()

#         if existing_group:
#             # Add the user to the existing group
#             existing_group.new_member(customer)
#             messages.success(request, "You have joined the group successfully.")
#         else:
#             # Create a new group
#             new_group = Group.objects.create(
#                 source=source,
#                 destination=destination,
#                 day_of_journey=day_of_journey,
#                 time_of_journey=time_of_journey,
#                 female_only=female_only,
#                 members=[customer.customer_id],
#                 created_by=customer  # This could also be the fallback user
#             )
#             messages.success(request, "You have successfully created the group.")

#         # Redirect back to the chatroom (refreshes the list of groups)
#         return redirect('chatroom')

#     return render(request, 'chatroom.html', {'groups': groups})


@login_required  # Ensures only authenticated users can create groups
def create_group(request):
    if request.method == "POST":
        user = request.user
        # Try to get the Customer profile or create one if it doesn’t exist
        customer, created = Customer.objects.get_or_create(user=user, defaults={
            "customer_name": user.username,
            "email": user.email,
            "phone_number": "",
            "gender": "Other",
            "profile_pic": "",
        })

        source = request.POST.get("source")
        destination = request.POST.get("destination")
        day_of_journey = request.POST.get("day_of_journey")
        time_of_journey = request.POST.get("time_of_journey")
        female_only = request.POST.get("female_only") == "on"

        # Save to database with created_by set
        group = Group.objects.create(
            source=source,
            destination=destination,
            day_of_journey=day_of_journey,
            time_of_journey=time_of_journey,
            female_only=female_only,
            created_by=customer  # Set the creator
        )

        return redirect("chatroom")

    return HttpResponseForbidden("403 Forbidden - Invalid request method")


@login_required
def chatroom(request, group_id=None):
    if group_id:
        # Handle group-specific view
        group = Group.objects.get(id=group_id)
        messages = group.messages.all()
        return render(request, 'chatroom_group.html', {'group': group, 'messages': messages})

    # Handle general chatroom
    groups = Group.objects.all()  # You can filter based on the user's available groups
    return render(request, 'chatroom.html', {'groups': groups})

@login_required
def pin_board(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    print(f"Logged-in User: {request.user.username}")
    print(f"Logged-in User Email: {request.user.email}")

    # Check if the Customer profile exists
    customer = Customer.objects.filter(email=request.user.email).first()

    # If the customer doesn't exist, create a new Customer profile
    if not customer:
        customer, created = Customer.objects.get_or_create(user=request.user, defaults={
            "customer_name": request.user.username,
            "email": request.user.email,
            "phone_number": "",
            "gender": "Other",
            "profile_pic": "",
        })
        # Redirect or display a message asking the user to complete registration
        if created:
            messages.info(request, "Customer profile created. Please complete your registration.")
    
    # Ensure the user is a member of the group
    if customer.customer_id not in group.members:
        messages.error(request, "You are not a member of this group.")
        return redirect('chatroom')

    if request.method == "POST":
        selected_message = request.POST.get("message")
        if selected_message:
            Message.objects.create(group=group, sender=customer, text=selected_message)
            messages.success(request, "Message sent!")
    
    # Fetch messages for the group
    group_messages = Message.objects.filter(group=group).order_by("-timestamp")

    return render(request, "pin_board.html", {"group": group, "messages": group_messages})
