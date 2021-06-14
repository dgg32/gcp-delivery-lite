import function
import json
import os
import numpy as np
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

import gcsfs

PROJECT = os.environ.get('PROJECT')

def main(event, context):
    """Triggered by a change to a Cloud Storage bucket.
    Args:
         event (dict): Event payload.
         context (google.cloud.functions.Context): Metadata for the event.
    """
    #print(f"E: {event}.")

    json_data = {}

    input_file = f"gs://{event['bucket']}/{event['name']}"

    gcs_file_system = gcsfs.GCSFileSystem(project=f"{PROJECT}")
    with gcs_file_system.open(input_file) as f:
        json_data = json.load(f)


    result = function.distance_matrix_gcp(json_data["destinations"])

    df_distance = result["distance_matrix"]

    #print (df_distance)

    distance_matrix = np.array(df_distance)

    data = {}

    # Create dictionnary with data
    
    # Distance Matrix
    data['distance_matrix'] = distance_matrix
    print("{:,} destinations".format(len(data['distance_matrix'][0]) - 1))
    # Orders quantity (Boxes)
    data['demands'] = [x["demand"] for x in json_data["destinations"]]
    # Vehicles Capacities (Boxes)
    data['vehicle_capacities'] = [x["capacity"] for x in json_data["carrier"]]
    # Fleet informations
    # Number of vehicles
    data['num_vehicles'] = len(data['vehicle_capacities'])
    # Location of the depot
    data['depot'] = 0

    # Create the routing index manager.
    manager = pywrapcp.RoutingIndexManager(len(data['distance_matrix']),
                                        data['num_vehicles'], data['depot'])

    # Calculate Distance between two nodes
    def distance_callback(from_index, to_index):
        """Returns the distance between the two nodes."""
        # Convert from routing variable Index to distance matrix NodeIndex.
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return data['distance_matrix'][from_node][to_node]
        
    # Get the order quantity of each node (location)
    def demand_callback(from_index):
        """Returns the demand of the node."""
        # Convert from routing variable Index to demands NodeIndex.
        from_node = manager.IndexToNode(from_index)
        return data['demands'][from_node]


    # Create Routing Model
    routing = pywrapcp.RoutingModel(manager)

    # Create and register a transit callback.
    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # Define cost of each arc.
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Add Capacity constraint.
    demand_callback_index = routing.RegisterUnaryTransitCallback(
        demand_callback)
    routing.AddDimensionWithVehicleCapacity(demand_callback_index,
        0,  # null capacity slack
        data['vehicle_capacities'],  # vehicle maximum capacities
        True,  # start cumul to zero
        'Capacity')

    # Setting first solution heuristic.
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH)
    search_parameters.time_limit.FromSeconds(1)

    # Solve the problem.
    solution = routing.SolveWithParameters(search_parameters)

    if solution:
        total_distance = 0
        total_load = 0
        for vehicle_id in range(data['num_vehicles']):
            index = routing.Start(vehicle_id)
            plan_output = f'Hello {json_data["carrier"][vehicle_id]["name"]}, your delivery route is the following:\n<br>'

            
            route_distance = 0
            route_load = 0
            while not routing.IsEnd(index):
                node_index = manager.IndexToNode(index)
                route_load += data['demands'][node_index]
                plan_output += f' {data["demands"][node_index]} Parcels to {json_data["destinations"][node_index]["address"]} -> <br>'
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                route_distance += routing.GetArcCostForVehicle(
                    previous_index, index, vehicle_id)
            plan_output += f' {manager.IndexToNode(index)} Parcels({route_load})\n<br>'
            plan_output += f'Distance of the route: {route_distance} (m)\n<br>'
            plan_output += f'Parcels Delivered: {route_load} (parcels)<br>'
            print(plan_output)

            carrier_email = json_data["carrier"][vehicle_id]["email"]
            function.send_email(carrier_email, "Your delivery route", plan_output)

            total_distance += route_distance
            total_load += route_load
        print(f'Total distance of all routes: {total_distance} (m)')
        print(f'Parcels Delivered: {total_load}/{sum(data["demands"])}')
    else:
        print('No Solution')



#main({}, {})