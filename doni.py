yosh = int(input("Yoshingizni kiriting: "))

if yosh >= 18:
    print("siz voyaga yetgansiz! ")
elif yosh <= 18:
    print("siz voyaga yetmagansiz! ")

################

son = int(input("Son kiriting: "))

if son % 2 == 0:
    print("Bu son juft son")
else:
    print("Bu son toq son")


###############

baho = int(input("bahoni kiriting: "))
if baho >= 90:
    print("A")
elif baho >= 80:
    print("B")
elif baho >= 70:
    print("C")
elif baho >= 60:
    print("D")
else:
    print("F")


################

son1 = int(input("Birinchi sonni kiriting: "))
son2 = int(input("Ikkinchi sonni kiriting: "))

if son1 > son2:
    print(f"{son1} soni {son2} sonidan katta")
elif son2 > son1:
    print(f"{son2} soni {son1} sonidan katta")
else:
    print("Ikkala son ham teng")