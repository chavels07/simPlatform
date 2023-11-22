import os
from xml.etree import ElementTree as ET

# PATH = os.getcwd() + '/statistics'
PATH = '../../data/statistics'


def get_avg_delay(index, scene_name_list: list):

    delay_dict = {}
    for scene_name in scene_name_list:
        filepath = PATH + '/' + str(index) + '/' + scene_name + '_statistics.xml'
        tree = ET.parse(filepath)
        root = tree.getroot()
        vehicle_trip_stats = root.find('vehicleTripStatistics')
        avg_delay = float(vehicle_trip_stats.attrib.get('timeLoss'))
        delay_dict[scene_name] = avg_delay
    return delay_dict


def get_total_stops(index, scene_name_list: list):

    stop_dict = {}
    for scene_name in scene_name_list:
        filepath = PATH + '/' + str(index) + '/' + scene_name + '_tripinfo.xml'
        tree = ET.parse(filepath)
        root = tree.getroot()
        total_stop = 0
        for trip in root:
            stop = int(trip.attrib.get('waitingCount'))
            total_stop += stop
        stop_dict[scene_name] = total_stop
    return stop_dict


def get_max_queue(index, scene_name_list: list):

    add_length: dict = {'E': {0: 223.83, 1: 131.84, 2: 83.02, 3: 25.75},
                        'W': {0: 275.81, 1: 256.25, 2: 141.82, 3: 20.5},
                        'N': {0: 81.4, 1: 0},
                        'S': {0: 106.37, 1: 62.3, 2: 0},
                        }
    queue_dict = {}
    for scene_name in scene_name_list:
        filepath = PATH + '/' + str(index) + '/' + scene_name + '_e2detectorinfo.xml'
        tree = ET.parse(filepath)
        root = tree.getroot()
        queue_info = {'E': [10, 0, 0.], 'W': [10, 0, 0.], 'N': [10, 0, 0.], 'S': [10, 0, 0.]}   # [sector, lane, length]
        for detector in root:
            detector_id = detector.attrib.get('id')
            approach = detector_id.split('_')[1][0]
            sector = int(detector_id.split('_')[1][1])
            lane = int(detector_id.split('_')[1][2])
            queue_length = float(detector.attrib.get('maxJamLengthInMeters'))
            if queue_length > 0:    # 有效数据
                if sector <= queue_info[approach][0]:
                    queue_info[approach][0] = sector
                    if queue_length > queue_info[approach][2]:
                        queue_info[approach][2] = queue_length
                        queue_info[approach][1] = lane
        max_queue_info = {}
        for approach, (sector, lane, length) in queue_info.items():
            real_length = length + add_length[approach][sector]
            # max_queue_info[approach] = (lane, real_length)
            max_queue_info[approach] = real_length
        queue_dict[scene_name] = max_queue_info
    return queue_dict


def get_throughput(index, scene_name_list: list):

    throughput_dict = {}
    for scene_name in scene_name_list:
        filepath = PATH + '/' + str(index) + '/' + scene_name + '_e1detectorinfo.xml'
        tree = ET.parse(filepath)
        root = tree.getroot()
        throughput = 0
        for detector in root:
            vehicle_num = int(detector.attrib.get('nVehContrib'))
            throughput += vehicle_num
        throughput_dict[scene_name] = throughput
    return throughput_dict


def get_stats(index, scene_name_list: list):

    delay = get_avg_delay(index, scene_name_list)
    stop_times = get_total_stops(index, scene_name_list)
    max_queue = get_max_queue(index, scene_name_list)
    throughput = get_throughput(index, scene_name_list)

    print(f'The average delay of the intersection is {delay}')
    print(f'The number of total stop times of all vehicles is {stop_times}')
    print(f'The throughput of the intersection is {throughput}')
    print(f'The max queue of each approach is {max_queue}')


if __name__ == '__main__':

    run_index = 32
    scenes = ['demand_high', 'demand_imbalance', 'demand_low']

    delay = get_avg_delay(run_index, scenes)
    stop_times = get_total_stops(run_index, scenes)
    max_queue = get_max_queue(run_index, scenes)
    throughput = get_throughput(run_index, scenes)

    print(f'The average delay of the intersection is {delay}')
    print(f'The number of total stop times of all vehicles is {stop_times}')
    print(f'The max queue of each approach is {max_queue}')
    print(f'The throughput of the intersection is {throughput}')
