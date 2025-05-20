import random

def derangement(n):
    lst = list(range(1, n + 1))
    deranged = lst[:]

    random.shuffle(deranged)

    for i in range(n):
        if lst[i] == deranged[i]:
            for j in range(n):
                if lst[j] != deranged[i] and lst[i] != deranged[j]:
                    deranged[i], deranged[j] = deranged[j], deranged[i]
                    break

    return deranged

n = int(input("Enter the number of guests: "))
result = derangement(n)
print("Visitantes ->   Carta recibida")
print("-" * 25)
guest = 1
for card in result:
    print("{:<10}->   {}".format(guest, card))
    guest += 1
