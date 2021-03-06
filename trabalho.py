import numpy as np
import cv2
import math
from os import listdir
from os.path import isfile, join
import os
import subprocess
import random
from skimage.transform import resize

IMG_PATH = "./Images/"
OUTPUT_PATH = "./output/"
PROCESSEC_RESULTS_PATH = OUTPUT_PATH + "results/"
TEMP_OUTPUT = "./temp/"

# recebe uma imagem e a mostra
def displayImg(img, windowname = "window"):
    cv2.imshow(windowname, img)
    cv2.waitKey(0)

# cria o path de saida caso ele nao exista
def createPath(path, silentError=True):
    try:
        os.makedirs(path)
    except OSError:
        if not silentError:
            print(OSError)

# salva a imagem
def saveResult(img, outputPath, saveMiniature=False):
    createPath(PROCESSEC_RESULTS_PATH)
    cv2.imwrite(outputPath, img)
    if saveMiniature:
        cv2.imwrite(outputPath[:-4] + ".min.png", cv2.resize(img, (int(img.shape[1]/2), int(img.shape[0]/2))))

# executa o camando do bash passado como argumento
def runBashCommand(command):
    process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
    output, error = process.communicate()
    return output

# aplica o filtro gamma na imagem
def applyGamma(img, gamma=1.5):
    invGamma = 1/gamma
    table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
    return np.uint8(0.75 * cv2.LUT(img, table))

# aplica filtros gaussianos de tamnha 3, 5, 7 e 9 na imagem
def applyGaussFilter(img):
    filterSizes = [3, 5, 7, 9]
    return [(cv2.GaussianBlur(img, (fSize, fSize), cv2.BORDER_DEFAULT), fSize/(2 * math.sqrt(2 * math.log(2)))) for fSize in filterSizes] + [(img, 1/(2 * math.sqrt(2 * math.log(2))))]

# executa o programa mindtct e salva o arquivo binario gerado pelo mesmo em formato png
def saveGauss(imgsWithGauss, subDirectory=''):
    createPath(OUTPUT_PATH + subDirectory)
    arrSize = len(imgsWithGauss)
    # imagem onde se calculara a media das imagens binarizadas
    imgMean = np.zeros(shape = imgsWithGauss[0][0].shape)
    for i, (item) in enumerate(imgsWithGauss):
        IMG_NAME = "gauss-"+str(i)
        IMG_PATH_NAME = OUTPUT_PATH + subDirectory + IMG_NAME
        IMG_FULL_NAME_PNG = IMG_PATH_NAME+"/"+IMG_NAME+".png"
        IMG_FULL_NAME_BINARY_RESULT = IMG_FULL_NAME_PNG[:-4]
        IMG_FULL_NAME_BYNARY_TO_PNG = IMG_FULL_NAME_BINARY_RESULT + ".brw"

        # cria o diretorio que ira armazenar os arquivos do valor corrente do filtro gaussiano
        createPath(IMG_PATH_NAME)

        # salva a imagem filtrada
        cv2.imwrite(IMG_FULL_NAME_PNG, item[0])

        # executa o software que faz a binariazacao
        runBashCommand("mindtct " + IMG_FULL_NAME_PNG + " " + IMG_FULL_NAME_BINARY_RESULT)

        # tranforma de binary raw para png
        result = saveBinary(IMG_FULL_NAME_BYNARY_TO_PNG, item[0].shape)
        imgMean += result
    # retorna a media das imagens binarizadas
    return np.uint8(imgMean / arrSize)

# salva as imagens passadas como paramento
def saveIntermediaryImgs(imgArr, outputPath, saveMiniature=False):
    for item in imgArr:
        saveResult(item[1], outputPath + item[0], saveMiniature)

# recebe um path de um arquivo binario e o salva convertido para imagem
def saveBinary(imgPath, imgShape):
    fd = open(imgPath, 'rb')
    rows = imgShape[0]
    cols = imgShape[1]
    f = np.fromfile(fd, dtype=np.uint8,count=rows*cols)
    im = f.reshape((rows, cols)) #notice row, column format
    fd.close()
    cv2.imwrite(imgPath[:-4]+"_binary.png", im)
    return im

# realiza a equializacao de histograma local
def localHistogramEqualization(img, blockSize=8):
    newImage = np.zeros(shape = img.shape)
    for i in range(0, img.shape[0], blockSize):
        for j in range(0, img.shape[1], blockSize):
            newImage[i: i+blockSize, j:j+blockSize] = cv2.equalizeHist(img[i:i+blockSize, j:j+blockSize])
    return np.uint8(newImage)

# retira as laterais brancas da imagem
def cropImage(img):
    mascara = (img<255)*1
    i, j = np.where(mascara == 0)
    maxH = max(i);
    minH = min(i);
    maxW = max(j);
    minW = min(j);
    return img[minH:maxH,minW:maxW]

# funcao que aumenta a largura do contorno superior da imagem a partir de uma equacao de grau N
# foi adaptada do algoritmo do professor zaghetto do link: https://github.com/zaghetto/Touchless2Touch/blob/master/geomDistor.m
def geomDistortion(img, N):
    H, W = img.shape
    new_vecw = detectPolyn(img, N)
    TamanhoNovaImagem = np.ceil(W+2*(max(new_vecw)-min(new_vecw)))+1
    ip = np.ones(shape = [H, int(round(TamanhoNovaImagem))])*255
    last_vecw = new_vecw.shape[0]

    if (last_vecw < H-1):
        for i in range(last_vecw, H-1):
            new_vecw = np.append(new_vecw, new_vecw[last_vecw-1])
    for i in range(0, H-1):
        li = resize(np.array([img[i,:]]).T, (int(W+2*(max(new_vecw) - new_vecw[i])),1))
        lisize = li.shape[0]
        ip[i,int(round((TamanhoNovaImagem-lisize)/2)):int(round((TamanhoNovaImagem-lisize)/2)+lisize)] = li.T;

    offset = int((ip.shape[1]-(W))/2)

    return np.uint8(ip[:, offset:offset + W] * 255)

# retorna duas imagens, uma fitrada para niveis acima do threshold e outra para niveis abaixo do threshold
def applyTreshHold(img, ths = 127):
    return (np.array([np.array([np.uint8(pixel) if pixel <= ths else np.uint8(255) for pixel in line]) for line in img]),
            np.array([np.array([np.uint8(pixel) if pixel >= ths else np.uint8(255) for pixel in line]) for line in img]))

# funcao de que definie a distribuicao de probabilidades da algoritmo de adicao de textura nas digitais
def getProbability(currentPlace, center, ths = 0.5):
    scaleFactor = 1 / (1 + abs(currentPlace - center)/300)
    randNum = random.random() * scaleFactor
    return randNum < ths

# funcao que gera um template contendo uma elipse gerada randomicamente
def getRandomElipse(template):
    x, y = template.shape
    center = (np.ceil(x/2), np.ceil(y/2))
    majorAxis = random.randint(1, 5)
    minorAxis = random.randint(1, 3)
    angulo = random.randint(0, 180)
    color = 255
    cv2.ellipse(template, (math.ceil(x/2), math.ceil(y/2)), (majorAxis, minorAxis), angulo, 0, 360, color, -1)
    return np.uint8(template)

# funcao principal de aplicacao de textura nas digitais
def applyRandomPatherns(img):
    height, width = img.shape
    center = int(width/2)
    newImage = img.copy()
    windowSize = 5
    probArray = []
    for i in range(0, height, windowSize):
        for j in range(0, width, windowSize):
            probabilitie = getProbability(j, center)
            if probabilitie:
                probArray.append((i,j))
                elipse = getRandomElipse(img[i: i+windowSize, j:j+windowSize])
                newImage[i:i+windowSize, j:j+windowSize] += elipse

    return np.uint8(newImage)

# calcula o polinomio usado na funcao de distorcao geometrica
# foi adaptada do algoritmo do professor zaghetto do link: https://github.com/zaghetto/Touchless2Touch/blob/master/detectPolyn.m
def detectPolyn(img, N):
    H, W = img.shape
    imf = np.uint8(np.ones(shape = img.shape)*255)
    vech = []
    vecw = []
    for i in range(0, H):
        for j in range(0, W):
            if (img[i,j] != 255):
                imf[i,j] = 0
                vech.append(i)
                vecw.append(j)
                break
    vech = np.asarray(vech)
    vecw = np.asarray(vecw)
    pol = np.polyfit(vech, -1*(vecw)+H,N)
    return np.polyval(pol, vech)

# funcao que faz a suavizacao de bordas das digitais
# foi adaptada do algoritmo do professor zaghetto do link: https://github.com/zaghetto/Touchless2Touch/blob/master/fadeCrop.m
def fadeCrop(img):
    grau = 2
    fade = 6

    h, w = img.shape
    x = np.array([i for i in range(0, 501, 50)])
    y = np.array([100, 80, 60, 50, 50, 50, 50, 50, 50, 50, 50])
    p = np.polyfit(x, y, grau)
    polinomio = np.polyval(p, np.array([[i for i in range(0, h+1)]]))
    polinomio = polinomio[0]
    somaFade = np.flip(np.array([i for i in range(0, 256, fade)]), 0)
    tamSomaFade = len(somaFade)

    cropped = np.ones(shape=img.shape) * 255
    for i in range(0, h):
        for j in range(0, w):
            if ((j > polinomio[ i ]) and (j < (w - polinomio[ i ]))):
                cropped[i, j] = img[i, j]
                if (math.ceil(j - polinomio[ i ]) <= tamSomaFade):
                    cropped[i, j] += somaFade[math.ceil(j - polinomio[ i ]) -1]
                if (math.ceil((w - polinomio[ i ]) - j) > 0 and math.ceil((w - polinomio[i]) - j) <= tamSomaFade):
                    cropped[i, j] += somaFade[math.ceil((w - polinomio[i]) - j) -1]
            if(cropped[i, j] > 255):
                cropped[i, j] = 255

    for j in range(0, w):
        for i in range(0, tamSomaFade):
            cropped[i, j] += somaFade[i]
            if(cropped[i, j] > 255):
                cropped[i, j] = 255

    somaFade = np.flip(somaFade, 0)

    for j in range(0, w):
        for i in range(h - tamSomaFade +1, h):
            cropped[i, j] += somaFade[i - h + tamSomaFade]
            if(cropped[i, j] > 255):
                cropped[i, j] = 255

    return np.uint8(cropped)

# funcao principal de processamento da digital
def tranformFingerprint(imgpath, outputSubdirectory):
    img = cv2.imread(imgpath, cv2.IMREAD_GRAYSCALE)
    equalizedImg = localHistogramEqualization(img)
    imgWithGamma = applyGamma(equalizedImg)
    imgsWithGauss = applyGaussFilter(imgWithGamma)
    binaryMean = saveGauss(imgsWithGauss, outputSubdirectory)
    height, width = binaryMean.shape

    cropImg = cropImage(binaryMean)
    imgDistortion = geomDistortion(cropImg, 5)
    thresholdLowImg, thresholdHighImg = applyTreshHold(imgDistortion, 80)

    bubbledImg = applyRandomPatherns(thresholdLowImg)
    overlayImg = cv2.addWeighted(bubbledImg, 0.9, thresholdHighImg, 0.2, 0)
    result = fadeCrop(overlayImg)

    # salva as imagens intermediarias geradas no processo de tranformacao da digital
    imgArr = [
        (outputSubdirectory+"-gamma.png", imgWithGamma),
        (outputSubdirectory+"-binary.png", binaryMean),
        (outputSubdirectory+"-distortion.png", imgDistortion),
        (outputSubdirectory+"-equalizedImg.png", equalizedImg),
        (outputSubdirectory+"-bubbled.png", overlayImg)
    ]
    saveIntermediaryImgs(imgArr, OUTPUT_PATH)
    return result

def processAllFingerPrints():
    # processa imagens
    images = [f for f in listdir(IMG_PATH) if isfile(join(IMG_PATH, f))]
    for index, (img) in enumerate(images):
        result = tranformFingerprint(IMG_PATH + img, img[:-4] + "/")
        saveResult(result, PROCESSEC_RESULTS_PATH + img[:-4] + ".png")

    # faz o score das imagens geradas
    processedImages = [f for f in listdir(PROCESSEC_RESULTS_PATH) if isfile(join(PROCESSEC_RESULTS_PATH, f))]
    for img in processedImages:
        print(int(runBashCommand("nfiq " + PROCESSEC_RESULTS_PATH + img)))

def main():
    processAllFingerPrints()

main()
