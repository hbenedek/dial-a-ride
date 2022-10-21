import numpy as np
import logging
import torch
import re

def float_equality(f1: float, f2: float, eps: float=0.001) -> bool:
    return abs(f1 - f2) < eps

def distance(pos1: np.ndarray, pos2: np.ndarray) -> float:
    return np.linalg.norm(pos1 - pos2)

def coord2int(coord: float) -> int:
    """given a float transforms it to integer representation"""
    number_precision = 3
    new_coord = int(round(coord, number_precision)*(10**number_precision))
    return new_coord

def get_device() -> str:
    if torch.cuda.is_available(): 
        device = 'cuda:0'
    else:
        device = 'cpu'
    return device


if __name__ == "__main__":
    pass