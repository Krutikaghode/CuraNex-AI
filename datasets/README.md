# Datasets

## pima_diabetes.csv

Pima Indians Diabetes Database (National Institute of Diabetes and Digestive and Kidney
Diseases), 768 rows, public and de-identified. Originally distributed via the UCI Machine
Learning Repository; this copy was taken from
`https://raw.githubusercontent.com/jbrownlee/Datasets/master/pima-indians-diabetes.data.csv`
(SHA-256 of the headerless original:
`6bfe5d0f379d17a0e0819b996407e3c09bf80febd4287f2ed212190dfff154af`) with a header row added.

| Column | Meaning |
|---|---|
| pregnancies | Number of pregnancies |
| glucose | Plasma glucose, 2 h oral glucose tolerance test (mg/dL) |
| blood_pressure | Diastolic blood pressure (mm Hg) |
| skin_thickness | Triceps skin fold thickness (mm) |
| insulin | 2-hour serum insulin (mu U/mL) |
| bmi | Body mass index (kg/m²) |
| diabetes_pedigree | Diabetes pedigree function |
| age | Age (years) |
| outcome | 1 = diabetes onset within 5 years |

Zeros in glucose, blood_pressure, skin_thickness, insulin and bmi are physiologically
impossible and mean "not measured"; training treats them as missing.

Limitations: all subjects are female, of Pima heritage, aged 21+. The model does not
generalise beyond that population, which is one more reason this project is a demo only.
