from NGO import NGO

def check_ngo(ngo, item):
    food = item.get("food_type", "")
    amount = float(item.get("amount", 0.0))
    
    if food not in ngo.food_list:
        return False, f"Food type '{food}' not accepted by {ngo.name}"
        
    if ngo.capacity < amount:
        return False, f"Not enough capacity (Available: {ngo.capacity}kg, Required: {amount}kg)"
        
    return True, "OK"

def filter_ngos(ngos, item):
    if not ngos:
        ngos = NGO.get_static_ngos()

    accept = []
    not_accept = []
    
    for ngo in ngos:
        ok, msg = check_ngo(ngo, item)
        if ok:
            accept.append(ngo)
        else:
            not_accept.append({
                "name": ngo.name,
                "reason": msg
            })
            
    return accept, not_accept