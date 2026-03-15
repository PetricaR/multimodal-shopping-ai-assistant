"""
Utility to generate generic baskets and user profiles for testing product substitution.
All content is in Romanian as requested.
"""
from typing import List, Dict
import random

def get_generic_baskets() -> Dict[str, List[Dict]]:
    """Returns a set of common shopping baskets in Romania"""
    return {
        "mic_dejun_sanatos": [
            {"product_id": "b1", "product_name": "Iaurt Grecesc Olympus 10% grăsime", "category": "Lactate", "price": 4.5, "quantity": 2},
            {"product_id": "b2", "product_name": "Afine proaspete 125g", "category": "Fructe", "price": 12.0, "quantity": 1},
            {"product_id": "b3", "product_name": "Fulgi de ovăz bio 500g", "category": "Cereale", "price": 8.5, "quantity": 1},
            {"product_id": "b4", "product_name": "Miere de salcâm Apicola", "category": "Miere", "price": 25.0, "quantity": 1}
        ],
        "cina_italiana": [
            {"product_id": "i1", "product_name": "Paste Barilla Spaghetti n.5", "category": "Paste", "price": 7.2, "quantity": 2},
            {"product_id": "i2", "product_name": "Sos de roșii cu busuioc Mutti", "category": "Conserve", "price": 9.5, "quantity": 1},
            {"product_id": "i3", "product_name": "Brânză Parmesan Reggiano", "category": "Brânzeturi", "price": 35.0, "quantity": 1},
            {"product_id": "i4", "product_name": "Ulei de măsline extra virgin Monini", "category": "Ulei", "price": 45.0, "quantity": 1}
        ],
        "gratar_weekend": [
            {"product_id": "g1", "product_name": "Mici proaspeți Gusturi Românești", "category": "Carne", "price": 18.0, "quantity": 2},
            {"product_id": "g2", "product_name": "Cârnați de Pleșcoi", "category": "Carne", "price": 22.0, "quantity": 1},
            {"product_id": "g3", "product_name": "Bere Ursus Premium 6-pack", "category": "Băuturi", "price": 28.0, "quantity": 1},
            {"product_id": "g4", "product_name": "Muștar de Tecuci", "category": "Sosuri", "price": 4.5, "quantity": 1}
        ],
        "curatenie_casa": [
            {"product_id": "c1", "product_name": "Detergent Ariel All-in-One Pods", "category": "Curățenie", "price": 85.0, "quantity": 1},
            {"product_id": "c2", "product_name": "Balsam de rufe Lenor Spring", "category": "Curățenie", "price": 18.0, "quantity": 1},
            {"product_id": "c3", "product_name": "Soluție geamuri Sano", "category": "Curățenie", "price": 12.5, "quantity": 1}
        ]
    }

def get_user_profiles() -> Dict[str, Dict]:
    """Returns typical user profiles for Romanian shoppers"""
    return {
        "fan_bio": {
            "user_id": "u1",
            "name": "Maria Enache",
            "preferences": "Preferă produse bio, organice și locale (Gusturi Românești).",
            "history": [
                {
                    "order_id": "o1",
                    "items": [
                        {"product_name": "Lapte Bio Carrefour", "producer": "Carrefour Bio", "price": 8.5},
                        {"product_name": "Ouă de țară", "producer": "Fermă locală", "price": 15.0},
                        {"product_name": "Mere Ionatan", "producer": "Producător local", "price": 5.0}
                    ]
                }
            ]
        },
        "buget_familie": {
            "user_id": "u2",
            "name": "Andrei Popescu",
            "preferences": "Caută promoții, branduri proprii accesibile (Simpl sau Carrefour Classic).",
            "history": [
                {
                    "order_id": "o2",
                    "items": [
                        {"product_name": "Ulei floarea soarelui Simpl", "producer": "Simpl", "price": 5.5},
                        {"product_name": "Zahăr tos Simpl", "producer": "Simpl", "price": 4.0},
                        {"product_name": "Pâine feliată", "producer": "Vel Pitar", "price": 3.5}
                    ]
                }
            ]
        },
        "premium_gourmet": {
            "user_id": "u3",
            "name": "Elena Radu",
            "preferences": "Apreciază brandurile premium, brânzeturi fine și vinuri de calitate.",
            "history": [
                {
                    "order_id": "o3",
                    "items": [
                        {"product_name": "Brânză Camembert Ile de France", "producer": "Ile de France", "price": 22.0},
                        {"product_name": "Prosciutto di Parma", "producer": "Negroni", "price": 18.5},
                        {"product_name": "Vin alb sec Purcari", "producer": "Purcari", "price": 55.0}
                    ]
                }
            ]
        }
    }

def generate_random_user_history(profile_type: str = "fan_bio") -> List[Dict]:
    """Helper to get history directly for the API"""
    profiles = get_user_profiles()
    profile = profiles.get(profile_type, profiles["fan_bio"])
    return profile["history"]
