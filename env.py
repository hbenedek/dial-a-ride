from collections import deque
from typing import Deque, Optional, Tuple, List, Dict
from collections import deque
from utils import float_equality, distance
import numpy as np
import gym

class Request():
    def __init__(self, id: int, pickup_position: np.ndarray, dropoff_position: Optional[np.ndarray], start_window: np.ndarray, end_window: Optional[np.ndarray], max_ride_time: int):
        self.id = id
        self.pickup_position = pickup_position
        self.dropoff_position = dropoff_position
        self.start_window = start_window
        self.end_window = end_window
        self.max_ride_time = max_ride_time
        self.state = "pickup"

    def __repr__(self):
        return f"Request_{self.id}_status:{self.state}"

    def __str__(self):
        return f"Request_{self.id}_status:{self.state}"

    def check_window(self, current_time: float, start: bool) -> bool:
        if start:
            start, end = self.start_window
        else:
            start, end = self.end_window
        if float_equality(current_time, start) or float_equality(current_time, end):
            return True
        return start <= current_time and end >= current_time

    def set_state(self, state: str):
        self.state = state



class Vehicle():
    def __init__(self, id: int, position: np.ndarray, capacity: int, max_route_duration: int):
        self.id = id
        self.position = position
        self.capacity = capacity
        self.max_route_duration = max_route_duration
        self.state: str = "waiting"
        self.trunk: Deque[Request] = deque()
        self.dist_to_destination: float = 0
        self.destination = np.empty(2)

    def __repr__(self):
        return f"Vehicle_{self.id}_status:{self.state}"

    def __str__(self):
        return f"Vehicle_{self.id}_status:{self.state}"

    def get_distance_to_destination(self) -> float:
        return distance(self.position, self.destination)

    def move(self, new_position: np.ndarray):
        self.position = new_position

    def pickup_request(self, request: Request, current_time: float):
        if len(self.trunk) < self.capacity:
            if request.check_window(current_time, start=True):
                self.trunk.append(request)
                request.set_state("in_trunk")

    def dropoff_request(self):
            request = self.trunk.popleft()
            request.set_state("delivered")

    def set_state(self, state: str):
        self.state = state


class DarpEnv(gym.Env):
    """Custom Environment that follows gym interface"""

    def __init__(self,
                size: int,
                nb_requests: int,
                nb_vehicles: int,
                time_end: int,
                max_step: int,
                max_route_duration: Optional[int]=None,
                capacity: Optional[int]=None,
                max_ride_time: Optional[int]=None,
                seed: Optional[int]=None,
                dataset: Optional[str]=None):
        super(DarpEnv, self).__init__()

        self.size = size
        self.max_step = max_step
        self.nb_requests = nb_requests
        self.nb_vehicles = nb_vehicles
        self.max_route_duration = max_route_duration
        self.capacity = capacity
        self.max_ride_time = max_ride_time
        self.time_end = time_end
        self.action_space = gym.spaces.Discrete(nb_requests + 1) #TODO: not sure if we need the gym space stuff
        self.observation_space = gym.spaces.Box(low=-self.size,
                                                high=self.size,
                                                shape=(self.size + 1, self.size + 1),
                                                dtype=np.int16)
        self.current_episode = 0
        self.current_step = 0
        self.current_time = 0
        self.last_time_gap = 0 #difference between consequtive time steps
        self.datadir = dataset
        self.seed = seed

        self.start_depot = None
        self.end_depot = None
       
        vehicles, requests = self.populate_instance()
        self.vehicles = vehicles
        self.requests = requests
        self.waiting_vehicles = [vehicle.id for vehicle in self.vehicles]
        self.current_vehicle = self.waiting_vehicles[0]
        self.destination_dict = self.output_to_destination()
        self.coordinates_dict = self.coodinates_to_requests()

        #make index to coordinate dict

    def output_to_destination(self) -> Dict[int, np.ndarray]:
        """"
        the Transformer, given a state configuration, for the current player outputs a probability distribution of the next potential target nodes
        this function converts the output index to destination coordinates 
        """
        pickups = {i: r.pickup_position for i, r in enumerate(self.requests)}
        dropoffs = {i + self.nb_requests: r.pickup_position for i, r in enumerate(self.requests)}
        depots = {self.nb_requests * 2: self.start_depot, self.nb_requests * 2 + 1: self.end_depot}
        return pickups.update(dropoffs).update(depots)

    def coodinates_to_requests(self) -> Dict[np.ndarray, Request]:
        pickups = {r.pickup_position: r for r in self.requests}
        dropoffs = {r.dropoff_position: r for r in self.requests}
        return pickups.update(dropoffs)


    def populate_instance(self) -> Tuple[List[Vehicle], List[Request]]:
        """"
        the function returns a list of vehicle and requests instances 
        depending either by random generating or loading a cordeau instance
        """
        return self.parse_data() if self.datadir else self.generate_instance()


    def generate_instance(self, window=None) -> Tuple[List[Vehicle], List[Request]]:
        """"generates random pickup, dropoff and other constraints, a list parsed of Vehicle and Request objects"""
        if self.seed:
            np.random.seed(self.seed)

        target_pickup_coodrs = np.random.uniform(-self.size, self.size, (self.nb_requests, 2))
        target_dropoff_coords = np.random.uniform(-self.size, self.size, (self.nb_requests, 2))

        #generate depot coordinates
        self.start_depot = np.random.uniform(-self.size, self.size, 2)
        self.end_depot = np.random.uniform(-self.size, self.size, 2)

        #generate time window constraints
        if window:
            pass #TODO: generate somehow time window conditions
            # (start + dist < end, 50% free start, 50% free end???)
        else:
            start_window = np.array([0, self.time_end])
            end_window = np.array([0, self.time_end])

        #init Driver and Target instances
        vehicles = []
        for i in range(self.nb_vehicles):
            driver = Vehicle(id=i,
                            position=self.start_depot,
                            capacity=self.capacity,
                            max_route_duration=self.max_route_duration)
            vehicles.append(driver)

        requests = []
        for i in range(self.nb_requests):
            request = Request(id=i,
                            pickup_position=target_pickup_coodrs[i],
                            dropoff_position=target_dropoff_coords[i],
                            #represents the earliest and latest time, which the service may begin
                            start_window=start_window,
                            end_window=end_window,
                            max_ride_time=self.max_ride_time)
            requests.append(request)
        return vehicles, requests
        

    def parse_data(self) -> Tuple[List[Vehicle], List[Request]]:
        """given a cordeau2006 instance, the function returns a list parsed of Vehicle and Request objects"""
        file_name = self.datadir
        with open(file_name, 'r') as file :
            number_line = sum(1 if line and line.strip() else 0 for line in file if line.rstrip()) - 3
            file.close()

        with open(file_name, 'r') as file :
            nb_vehicles, nb_requests, max_route_duration, capacity, max_ride_time = list(map(int, file.readline().split()))

            if nb_requests != self.nb_requests:
                raise ValueError(f"DarpEnv.nb_requests={self.nb_requests} does not coincide with {nb_requests}")

            #Depot
            _, depo_x, depo_y, _, _, _, _ = list(map(float, file.readline().split()))
            self.start_depot = np.array([depo_x, depo_y])
            self.end_depot = np.array([depo_x, depo_y])

            #Init vehicles
            vehicles = []
            for i in range(nb_vehicles):
                vehicle = Vehicle(id=i,
                            position=self.start_depot,
                            capacity=capacity,
                            max_route_duration=max_route_duration)
                vehicles.append(vehicle)

            #Init requests
            requests = []
            for l in range(number_line):
                #parsing line 1, ...,n
                if l < number_line // 2:
                    identity, pickup_x, pickup_y, _, _, start_tw, end_tw = list(map(float, file.readline().split()))
              
                    request = Request(id=identity + 1,
                                pickup_position=np.array([pickup_x, pickup_y]),
                                dropoff_position=None,
                                #represents the earliest and latest time, which the service may begin
                                start_window=np.array([start_tw, end_tw]),
                                end_window=None,
                                max_ride_time=max_ride_time)
                   
                    requests.append(request)
                #parsing line n+1, ..., 2n
                else:
                    _, dropoff_x, dropoff_y, _, _, start_tw, end_tw = list(map(float, file.readline().split()))
                    request = requests[l - number_line // 2]
                    request.dropoff_position = np.array([dropoff_x, dropoff_y])
                    request.end_window = np.array([start_tw, end_tw])

        return vehicles, requests

    def representation(self):
        pass

    def take_action(self, action: int):
        """ Action: destination point as an indice of the map vactor. (Ex: 1548 over 2500)"""
        current_vehicle = self.vehicles[self.current_vehicle]
        current_vehicle.destination =  self.destination_dict(action)
        pass

    def update_time_step(self):
        "For each vehicle queries the next decision time and sets the current time attribute to the minimum of these values"
        events = [0, self.time_end]
        for vehicle in self.vehicles:
            event = vehicle.get_distance_to_destination()
            event.append(event)

        events = [event for event in events if event > self.current_time]
        new_time = min(events)
        self.last_time_gap = new_time - self.current_time
        self.current_time = new_time


    def update_vehicle_position(self):
        for vehicle in self.vehicles:
            dist_to_destination = vehicle.get_distance_to_destination()
            if float_equality(self.last_time_gap, dist_to_destination, eps=0.001):
                #vehicle arraving to destination
                vehicle.move(vehicle.destination)

                #resolving pickup, dropoff or depot arrival
                request = self.coordinates_dict[vehicle.destination]
                if request.pickup_position == vehicle.position:
                    vehicle.pickup_request(request)
                    vehicle.set_state("busy")
                elif request.dropoff_position == vehicle.position:
                    vehicle.dropoff_request()
                    vehicle.set_state("waiting")
                elif self.end_depot == vehicle.position:
                    vehicle.set_state("finished")

            #move vehicle closer to its destination
            elif self.last_time_gap < vehicle.dist_to_destination:
                unit_vector = (vehicle.destination - vehicle.position) / vehicle.dist_to_destination
                new_position = vehicle.position + self.last_time_gap * unit_vector
                vehicle.move(new_position)

            else :
                raise ValueError(f"Could not update the position of {vehicle}")
            
            
    
    def step(self, action: int):
        self.take_action(action)
        self.current_step += 1

        if not self.waiting_vehicles:
            self.update_time_step()
            if self.last_time_gap > 0:
                self.update_vehicle_position()
            
            #Charge all players that may need a new destination
            for vehicle in self.vehicles:
                    if vehicle.status == 'waiting':
                        self.waiting_vehicles.append(vehicle.identity)

        self.current_vehicle = self.waiting_vehicles.pop()
        reward = #TODO: it should be the total distance, check B&C paper
        observation = self.next_observation()
        done = env.is_done()
        return observation, reward, done


    def is_done(self) -> bool:
        done = False
        return done

    def next_observation(self):
        pass

    def print_info(self):
        pass


if __name__ == "__main__":
    FILE_NAME = './data/cordeau/a2-16.txt'
    env = DarpEnv(size=10, nb_requests=16, nb_vehicles=2, time_end=1400, max_step=100, dataset=FILE_NAME)
    print(env.vehicles)
    print(env.requests)
    
        
    
 

